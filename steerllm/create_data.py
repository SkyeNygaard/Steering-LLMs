import os
from omegaconf import DictConfig, OmegaConf
import hydra
import time
from openai import OpenAI
import logging
import math
from jinja2 import Environment, FileSystemLoader



from dataset_creator import DatasetCreator

# Constants - things we don't want/need to configure in config.yaml
SRC_PATH = os.path.dirname(__file__)
DATA_PATH = os.path.join(os.path.dirname(SRC_PATH), 'data')



def get_user_response():
    print("\nAre you happy with this dataset prototype? (y/n)")
    while True:
        response = input("Enter your response: ").lower()
        if response in ['y', 'n']:
            return response
        else:
            print("Invalid input. Please enter 'y' or 'n'.")



@hydra.main(version_base=None, config_path=".", config_name="config_dataset.yaml")
def main(cfg: DictConfig) -> None: 

    api_key = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=api_key)

    # Load the LLM configuration for dataset creation
    model = cfg.llm_b_model_name
    temperature = cfg.temperature
    total_examples = cfg.total_examples
    examples_per_request = cfg.examples_per_request
    prototype_examples = cfg.prototype_examples

    # Load the dataset configuration info
    template_dir = os.path.join(DATA_PATH, "inputs/templates")
    dataset_template_dir = os.path.join(template_dir, "dataset_prompt_templates")
    header_labelling_template_dir = os.path.join(template_dir, "header_labelling_prompt_templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    rendered_prompts = {}
    rendered_header_labelling_pairs = {}

    for dataset_name, dataset_config in cfg.datasets.items():
        dataset_template_path = os.path.join(dataset_template_dir, dataset_config.dataset_prompt_template)
        dataset_template = env.get_template(dataset_template_path)
        dataset_prompt = dataset_template.render(**dataset_config.dataset_prompt_template_variables)
        rendered_prompts[dataset_name] = dataset_prompt
        dataset_header_labelling_pairs = {}

        for pair_name, pair_config in dataset_config.header_labelling_pairs.items():
            pair_template_path = os.path.join(header_labelling_template_dir, pair_config.hl_prompt_template)
            pair_template = env.get_template(pair_config.hl_prompt_template)
            pair_prompt = pair_template.render(**pair_config.hl_prompt_template_variables)
            dataset_header_labelling_pairs[pair_name] = pair_prompt

        rendered_header_labelling_pairs[dataset_name] = dataset_header_labelling_pairs

    print("Rendered Prompts:")
    print(rendered_prompts)

    print("\nRendered Header Labelling Pairs:")
    print(rendered_header_labelling_pairs)




    
    

#     # Create prompt by populating the jinja template
#     # with the values from the config file

#     dataset_creator = DatasetCreator(DATA_PATH)
#     dataset_dir = dataset_creator.create_output_directories(dataset_name)


#     test_prompt = dataset_creator.prompt_scaffolding(prompt, examples_per_request)   

#     # Generate the sample dataset

#     # First save the prompt as a text file
#     with open(dataset_dir+"/test_prompt.txt", 'w', newline='', encoding='utf-8') as file:
#         file.write(test_prompt)

#     # Define the file path for the generated dataset
#     generated_dataset_file_path = os.path.join(dataset_dir, f"{dataset_name}")

#     # Define the log file path
#     log_file_path = os.path.join(dataset_dir, "log")

#     # Generate sample dataset
#     start_time = time.time()
#     dataset_creator.generate_dataset_from_prompt(test_prompt,
#                                                  generated_dataset_file_path,
#                                                  client,
#                                                  model,
#                                                  temperature,
#                                                  log_file_path,
#                                                  0)
#     end_time = time.time()
#     elapsed_time = end_time - start_time
#     logging.info(f"The code took {elapsed_time} seconds to run.")

#     # See if the generated dataset is usable?
#     user_response = get_user_response()

#     if user_response == "y":
    
#         # Generate the full dataset if the user is happy with the prototype
#         num_iterations = math.ceil(total_examples/examples_per_request)
#         start_time = time.time()
#         # Generate the dataset
#         for i in range(num_iterations):
#             logging.info(f"Iteration {i}.")
#             dataset_creator.generate_dataset_from_prompt(test_prompt,
#                                                         generated_dataset_file_path,
#                                                         client,
#                                                         model,
#                                                         temperature,
#                                                         log_file_path,
#                                                         0)
#         end_time = time.time()
#         elapsed_time = end_time - start_time
#         logging.info(f"The code took {elapsed_time} seconds to run.")

#         # Compress the generated datasets into one csv file
#         dataset_creator.create_csv_unlabelled(generated_dataset_file_path)






if __name__ == "__main__":
    main()

