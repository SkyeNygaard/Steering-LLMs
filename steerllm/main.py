# Imports
import transformer_lens
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import os
import pickle
import torch
import sys
import sklearn
from sklearn.manifold import TSNE
from typing import Any
from dataclasses import dataclass
import datetime
import json

# Constants
PROMPT_COLUMN = "Prompt"
ETHICAL_AREA_COLUMN = "Ethical_Area"
POS_COLUMN = "Positive"
DATA_PATH = os.path.join("..", "data")
OUTPUT_PICKLE = os.path.join(DATA_PATH, "outputs", "activations_cache.pkl")
MODEL_NAME = "gpt2-small"
SEED = 42

# May need to install tkinter if not included
matplotlib.use('TkAgg')


# Store all relevant data for a given prompt within this class
# Can construct progressively, assign the data as it is processed
@dataclass
class Activation:
    prompt: str
    ethical_area: str
    positive: bool
    raw_activations: Any
    hidden_states: list[np.ndarray]


# Load ethical prompts
# Will work with csv or excel
def csv_to_dictionary(filename: str) -> dict[str, Any]:

    if filename.endswith(".csv"):
        df = pd.read_csv(filename)
    elif filename.endswith(".xlsx"):
        df = pd.read_excel(filename)
    else:
        raise Exception("Expected file ending with .csv or .xlsx")
    # df = df.dropna()
    data = df.to_dict(orient="list")

    return data


# Compute forward pass and cache data
def compute_activations(model: Any, activations_cache: list[Activation]) -> None:
    for act in activations_cache:
        # Run the model and get logits and activations
        logits, raw_activations = model.run_with_cache(act.prompt)
        act.raw_activations = raw_activations


# Load cached data from file
def load_cache(filename: str) -> Any:
    with open(filename, 'rb') as f:
        data = pickle.load(f)
    return data


# Add the hidden states (the weights of the model between attention/MLP blocks)
# Use the last token
# TODO: I am not sure if the "hidden layers" that pytorch gives for RepE are normalized or unnormalized
def add_numpy_hidden_states(activations_cache: list[Activation]) -> None:
    for act in activations_cache:
        raw_act = act.raw_activations
        for hook_name in raw_act:
            # Only get the hidden states, the last activations in the block
            if "hook_resid_post" in hook_name:
                # Convert to numpy array
                # calling .cpu() while using a cpu is a no-op. Needed if run with gpu
                numpy_activation = raw_act[hook_name].cpu().numpy()
                # Get only the last token activations using '-1'
                # print("numpy_activation.shape", numpy_activation.shape)
                act.hidden_states.append(numpy_activation[0][-1])


# Extract the data we are actually using from the dictionary
def populate_data(prompts_dict: dict[str, Any]) -> list[Activation]:
    activations_cache = []
    for prompt, ethical_area, positive in zip(prompts_dict[PROMPT_COLUMN],
                                              prompts_dict[ETHICAL_AREA_COLUMN],
                                              prompts_dict[POS_COLUMN]):
        act = Activation(prompt, ethical_area, bool(positive), None, [])
        activations_cache.append(act)
    return activations_cache




# Make tsne plot for hidden state of every layer
# For now, using the last layer, last token as representative embedding for input
def tsne_plot(activations_cache: list[Activation], images_dir: str) -> None:


    # Using activations_cache[0] is arbitrary as they all have the same number of layers
    # (12 with GPT-2) with representations
    for layer in range(len(activations_cache[0].hidden_states)):
        
        # print(f"layer {layer}")

        data = np.stack([act.hidden_states[layer] for act in activations_cache])
        labels = [f"{act.ethical_area} {act.positive}" for act in activations_cache]

        # print("data.shape", data.shape)

        tsne = TSNE(n_components=2, random_state=SEED)
        embedded_data = tsne.fit_transform(data)
        
        df = pd.DataFrame(embedded_data, columns=["X", "Y"])
        df["Ethical Area"] = labels
        ax = sns.scatterplot(x='X', y='Y', hue='Ethical Area', data=df)
        
        plot_path = os.path.join(images_dir, f"tsne_plot_layer_{layer}.png")
        plt.savefig(plot_path)

        plt.clf()


# Initialize output directory with timestamp
def create_output_directories() -> tuple[str, str]:
    current_datetime = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    experiment_base_dir = os.path.join(DATA_PATH, "outputs", current_datetime)
    images_dir = os.path.join(experiment_base_dir, 'images')

    os.makedirs(experiment_base_dir)
    os.makedirs(images_dir)

    return experiment_base_dir, images_dir


# Write cache data
def write_activations_cache(activations_cache: Any, experiment_base_dir: str) -> None:
    filename = os.path.join(experiment_base_dir, "activations_cache.pkl")
    with open(filename, 'wb') as f:
        pickle.dump(activations_cache, f)


# Write experiment parameters
# TODO: Replace with hydra
def write_experiement_parameters(experiment_params: dict, experiment_base_dir: str) -> None:
    with open(os.path.join(experiment_base_dir, "experiment_parameters.json"), 'w') as f:
        json.dump(experiment_params, f)

  

if __name__ == "__main__":
    model = transformer_lens.HookedTransformer.from_pretrained(MODEL_NAME)

    # Run with:
    # >>> python3 main.py ../data/inputs/prompts_good_evil_justice.xlsx
    # Check if a filename is provided as an argument
    # TODO: Use hydra for command line arguments
    if len(sys.argv) < 2:
        print("Please provide a filename as an argument.")
        sys.exit(1)

    # This dictionary will be used to track the parameters of the experiment.
    # We can add more to it. This is just a start.
    # It might be good to use Hydra to manage the parameters in a seperate
    # config file if we have a lot that changes from run to run. We'd have one
    # place where we know to go to change things. It also lets us seperate out
    # CONSTANTS at the top of the file from parameters that change.
    experiment_params = {
        'model_name': MODEL_NAME,
        'experiment_notes': "Testing out the transformer lens library."
    }

    experiment_base_dir, images_dir = create_output_directories()

    input_path = sys.argv[1]
    prompts_dict = csv_to_dictionary(input_path)

    # Copy the specific prompts being used from inputs to outputs.
    # Why? While we are still figuring out which prompt datasets work.
    # Prompt datasets as inputs which don't work will probably be deleted over time.
    # Saving them for a specific output lets us track which prompts were used for which output.
    # We can stop doing this once we have prompts that work.
    input_file_stem  = os.path.splitext(os.path.basename(input_path))[0]
    prompts_output_path = os.path.join(experiment_base_dir, f"{input_file_stem}.csv")
    prompts_df = pd.DataFrame(prompts_dict)
    prompts_df.to_csv(prompts_output_path)

    activations_cache  = populate_data(prompts_dict)

    # Can use pudb as interactive commandline debugger
    # import pudb; pu.db

    compute_activations(model, activations_cache)
    
    add_numpy_hidden_states(activations_cache)
    
    tsne_plot(activations_cache, images_dir)

    # Each transformer component has a HookPoint for every activation, which
    # wraps around that activation.
    # The HookPoint acts as an identity function, but has a variety of helper
    # functions that allows us to put PyTorch hooks in to edit and access the
    # relevant activation
    # Relevant when changing the model
    
    # TODO: Create the raster plot
    # np.digitize useful for raster plot - https://www.earthdatascience.org/courses/use-data-open-source-python/intro-raster-data-python/raster-data-processing/classify-plot-raster-data-in-python/
    # TODO: Cluster with PCS in addition to TSNE, figure out which are most simlar

    write_experiement_parameters(experiment_params, experiment_base_dir)

    write_activations_cache(activations_cache, experiment_base_dir)

