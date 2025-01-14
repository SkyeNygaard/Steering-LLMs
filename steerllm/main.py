# Imports

import matplotlib
import os
from omegaconf import DictConfig, OmegaConf
import hydra
import pickle

from data_handler import DataHandler
from data_analyser import DataAnalyzer
from model_handler import ModelHandler
from steering_handler import SteeringHandler

from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from sklearn.cluster import FeatureAgglomeration

import logging




# Constants
# If going forward with Hydra, we put everything here
# That really is constant betweeen runs.
# Everything that is configurable goes in config.yaml
# The model name is now there.
SRC_PATH = os.path.dirname(__file__)
DATA_PATH = os.path.join(SRC_PATH, "..", "data")
OUTPUT_PICKLE = os.path.join(DATA_PATH, "outputs", "activations_cache.pkl")
SEED = 42

# May need to install tkinter if not included
matplotlib.use('TkAgg')

    

@hydra.main(version_base=None, config_path=".", config_name="config_updated.yaml")
def main(cfg: DictConfig) -> None:  
    
    # Create a model handler
    # Instaitiate the model handler will load the model
    logging.info("Creating model handler to load the model")
    model_handler = ModelHandler(cfg)



    # Process data
    logging.info("Processing data")

    # Create a data handler
    data_handler = DataHandler(DATA_PATH)


    # Load the inputs (prompts)
    prompts_dict = data_handler.csv_to_dictionary(cfg.prompts_sheet)


    # Create output directories
    experiment_base_dir, images_dir, metrics_dir = data_handler.create_output_directories()


    # Copy the config.yaml file to the output directory and the prompts
    # Why? So we can see what the configuration was for a given run.
    # config.yaml will change from run to run, so we want to save it for each run.
    data_handler.write_experiment_parameters(cfg, prompts_dict, experiment_base_dir)

    activations_cache = data_handler.populate_data(prompts_dict)



    # Get activations
    logging.info("Getting activations")


    # Can use pudb as interactive commandline debugger
    # import pudb; pu.db
    
    
    data_analyzer = DataAnalyzer(images_dir, metrics_dir, SEED)
    steering_handler = SteeringHandler(cfg, model_handler, data_handler)
    rep_reader = None
    
    if cfg.steering.load:
        assert cfg.steering.file != ""
        full_path = os.path.join(DATA_PATH, cfg.steering.file)
        with open(full_path, 'rb') as f:
            # Load the object from the file
            rep_reader = pickle.load(f)

        # TODO: Add way to compute_activations to steering_handler
        # steering_handler.compute_activations(activations_cache)
        logging.info("Right now, we can only compute activations with non-steered model")

    # else:
    model_handler.compute_activations(activations_cache)


    if cfg.steering.write:
        # Steering
        logging.info("Running steering")
        hidden_layers = model_handler.get_hidden_layers()
        concept_H_tests, concept_rep_readers = steering_handler.compute_directions(prompts_dict, rep_token=-1)
        # Add function to data_handler
            
        data_analyzer.repreading_accuracy_plot(hidden_layers, concept_H_tests, concept_rep_readers)
        for concept, rep_reader in concept_rep_readers.items():
            # TODO Replace PCA with variable for method of generating steering vector
            # TODO: Right now this pickle is a giant file. Fix
            filename = os.path.join(experiment_base_dir, f"{cfg.model_name}_{concept}_PCA_rep_reader.pkl")
            with open(filename, 'wb') as f:
                pickle.dump(rep_reader, f)

    if cfg.evaluate_completion:
        assert cfg.steering.file != ""
        assert rep_reader is not None
        logging.info("Runing Control Pipeline")
        # TODO: Make input correspond to what we want to generate for
        base_continuation, control_continuation = steering_handler.control(rep_reader, input=activations_cache[0].prompt, layer_id=None)
        logging.info("Base Continuation")
        logging.info(base_continuation)
        logging.info("")
        logging.info("Control Continuation")
        logging.info(control_continuation)


    tsne_model = TSNE(n_components=2, random_state=42)
    tsne_embedded_data_dict, tsne_labels, tsne_prompts = data_analyzer.plot_embeddings(activations_cache, tsne_model)
    pca_model = PCA(n_components=2, random_state=42)
    pca_embedded_data_dict, pca_labels, pca_prompts = data_analyzer.plot_embeddings(activations_cache, pca_model)
    fa_model = FeatureAgglomeration(n_clusters=2)
    fa_embedded_data_dict, fa_labels, fa_prompts = data_analyzer.plot_embeddings(activations_cache, fa_model)

    # TODO: 
    # Would be good if our code could just take any valid
    # dimensionality reduction method from sci-kit learn.
    dimensionality_reduction_map = {
        'pca': PCA,
        'tsne': TSNE,
        'feature_agglomeration': FeatureAgglomeration,
        # Add more mappings as needed
    }



    # # Mapping of method names to their corresponding classes
    # # This assumes we have these classes imported correctly
    # # at the top of our file
    # dimensionality_reduction_map = {
    #     'pca': PCA,
    #     'tsne': TSNE,
    #     'feature_agglomeration': FeatureAgglomeration
    # }

    # results = {}
    # dim_red_methods = cfg.dim_red.methods

    # # Iterate through each dim red method and its configuration
    # for method_name, method_config in dim_red_methods.items():
    #     DimRedClass = dimensionality_reduction_map.get(method_name.lower())
        
    #     if not DimRedClass:
    #         print(f"{method_name} not found.")
    #         continue
        
    #     # Instantiate the model with parameters unpacked from method_config
    #     model = DimRedClass(**method_config)
        
    #     # Call the data_analyzer.plot_embeddings method with the model
    #     embedded_data_dict, labels, prompts = data_analyzer.plot_embeddings(activations_cache, model)
        
    #     # Store results
    #     results[method_name] = {
    #         'embedded_data_dict': embedded_data_dict,
    #         'labels': labels,
    #         'prompts': prompts
    #     }
    


    classifier_methods = OmegaConf.to_container(cfg.classifiers.methods, resolve=True)

    # See if the dimensionality reduction representations can be used to classify the ethical area
    # Why are we actually doing this? Hypothesis - better seperation of ethical areas
    # Leads to better steering vectors. This actually needs to be tested.
    for method_name, method_config in cfg.dim_red.methods.items():
        if method_name in dimensionality_reduction_map:
            # Prepare kwargs by converting OmegaConf to a native Python dict
            kwargs = OmegaConf.to_container(method_config, resolve=True)
            dr_class = dimensionality_reduction_map[method_name]
            dr_instance = dr_class(**kwargs)
            embedded_data_dict, labels, prompts = data_analyzer.plot_embeddings(activations_cache, dr_instance)
            # Now X_transformed can be used for further analysis or classification
            data_analyzer.classifier_battery(classifier_methods, embedded_data_dict, labels, prompts, dr_instance, 0.2)
        else:
            logging.warning(f"Warning: {method_name} is not a valid dimension reduction method or is not configured.")

    # Other dimensionality reduction related analysis
    logging.info("Running other dimensionality reduction related analysis")

    for method_name in cfg.other_dim_red_analyses.methods:
        if hasattr(data_analyzer, method_name):
            getattr(data_analyzer, method_name)(activations_cache)
        else:
            print(f"Warning: Method {method_name} not found in DataAnalyzer.")

    # Further analysis not based on dimensionality reduction
    logging.info("Running further analysis not based on dimensionality reduction")

    for method_name in cfg.non_dimensionality_reduction.methods:
        if hasattr(data_analyzer, method_name):
            getattr(data_analyzer, method_name)(activations_cache)
        else:
            print(f"Warning: Method {method_name} not found in DataAnalyzer.")


    
    # Activations cache takes up a lot of space, only write if user sets
    # parameter
    if cfg.write_cache:
        model_handler.write_activations_cache(activations_cache, experiment_base_dir)



if __name__ == "__main__":
    # Run with:
    # >>> python3 main.py prompts_sheet="../data/inputs/prompts_honesty_integrity_compassion.xlsx" model_name="meta-llama/Llama-2-7b-hf"
    main()

