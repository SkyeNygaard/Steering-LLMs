# Imports
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
import os

from typing import Any, List, Tuple, Dict
import logging
from dataclasses import dataclass

from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.random_projection import johnson_lindenstrauss_min_dim
from sklearn import cluster
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report
from sklearn import tree
from sklearn.base import BaseEstimator

from data_handler import Activation


class DataAnalyzer:
    """
    Manages the analysis of neural network activations, including dimensionality reduction,
    visualization, and performance evaluation of classifiers on the reduced data.

    This class provides a suite of tools to work with activations data extracted from neural
    networks, facilitating the exploration of how different layers of the network process
    information. 

    Parameters:
    -----------
    metrics_dir : str
        The directory path where output files (plots, metrics) will be saved.
    images_dir : str
        The directory path where image files will be saved.
    seed : int, optional
        An optional seed for random number generators to ensure reproducibility.

    Usage:
    ------
    Create an instance of AnalysisManager with a specified metrics directory. Then call
    its methods by passing in neural network activations data and other required parameters.
    """
    
    def __init__(self, images_dir: str, metrics_dir, seed: int = 42):
        self.images_dir = images_dir
        self.metrics_dir = metrics_dir
        self.seed = seed



    #############################################
    # DIMINSIONALITY REDUCTION ANALYSIS METHODS #
    #############################################

    def plot_embeddings(self, activations_cache: List[Activation], dim_red_model: Any) -> Tuple[Dict[int, np.ndarray], List[str], List[str]]:
        """
        Generates and saves plots from activations using the specified dimensionality
        reduction model to visualize the distribution of different ethical areas in
        the embedded space.

        Iterates over layers, applies the provided dimensionality reduction model for
        2D visualization, and saves scatter plots. Returns dictionaries of embedded data,
        labels, and prompts.

        Parameters
        ----------
        activations_cache : List[Activation]
            List of Activation objects with hidden states and metadata.
        dim_red_model : Any
            A dimensionality reduction model instance with a fit_transform method.

        Returns
        -------
        Tuple[Dict[int, np.ndarray], List[str], List[str]] 
            Tuple containing a dictionary of embedded data by layer, list of labels, and list of prompts.

        Outputs
        -------
        Saves PNG files of the scatter plots.
        """
        embedded_data_dict, all_labels, all_prompts = {}, [], []
        for layer in range(len(activations_cache[0].hidden_states)):
            data = np.stack([act.hidden_states[layer] for act in activations_cache])
            labels = [f"{act.ethical_area} {act.positive}" for act in activations_cache]
            prompts = [act.prompt for act in activations_cache]

            embedded_data = dim_red_model.fit_transform(data)
            embedded_data_dict[layer] = embedded_data

            if not all_labels:
                all_labels.extend(labels)
                all_prompts.extend(prompts)

            # Use a generic plot title incorporating the dim_red_model's class name
            plot_title = type(dim_red_model).__name__
            self._save_plot(embedded_data, labels, layer, plot_title)

        return embedded_data_dict, all_labels, all_prompts



    def _save_plot(self, embedded_data: np.ndarray, labels: List[str], layer: int, plot_title: str) -> None:
        """
        Saves a 2D scatter plot for the specified layer using given embeddings.

        Parameters
        ----------
        embedded_data : np.ndarray
            The 2D transformed data.
        labels : List[str]
            List of labels for each data point.
        layer : int
            The layer number the data corresponds to.
        plot_title : str
            The title of the plot indicating the dimensionality reduction technique used.

        Returns
        -------
        None

        Outputs
        -------
        Saves a PNG file of the scatter plot.
        """
        df = pd.DataFrame(embedded_data, columns=["X", "Y"])
        df["Ethical Area"] = labels
        plt.figure(figsize=(10, 8))
        sns.scatterplot(x='X', y='Y', hue='Ethical Area', palette='viridis', data=df)
        plot_path = os.path.join(self.images_dir, f"{plot_title.lower()}_plot_layer_{layer}.png")
        plt.savefig(plot_path)
        plt.close()



    def random_projections_analysis(self, activations_cache: list[Activation]) -> None:
        """
        Evaluates the minimum dimension for eps-embedding using random projections and
        prints the suggested dimensionality based on the Johnson-Lindenstrauss lemma.
        
        This function iterates over each layer in the activations cache, applying the 
        concept of random projections to the hidden states data. It calculates and logs 
        the minimal embedding dimension needed to preserve the pairwise distances between 
        the data points, within a factor of (1 ± eps), where eps is a small positive number.
        
        Parameters
        ----------
        activations_cache : list[Activation]
            A list of `Activation` objects, each containing the hidden states for each layer 
            of a model, along with associated metadata like ethical area and positivity flag. 
            It is assumed that all `Activation` objects contain the same number of layers.
        
        Returns
        -------
        None

        Outputs
        -------
        Prints the dataset size and the minimum embedding dimension suggested by the
        Johnson-Lindenstrauss lemma.
        """     

        # Define a range of epsilon values to test
        epsilon_values = [0.01, 0.05, 0.1, 0.2, 0.3]

        output_file_path = os.path.join(self.metrics_dir, "random_projection_dimensions.txt")
        with open(output_file_path, 'w') as output_file:

            for layer in range(len(activations_cache[0].hidden_states)):

                data = np.stack([act.hidden_states[layer] for act in activations_cache])
                labels = [f"{act.ethical_area} {act.positive}" for act in activations_cache]

                for epsilon in epsilon_values:
                    """
                    Calculate the minimum embedding dimension for the current epsilon
                    Note that the number of dimensions is independent of the original number of features 
                    but instead depends on the size of the dataset: the larger the dataset, 
                    the higher is the minimal dimensionality of an eps-embedding.
                    """
                    min_dim = johnson_lindenstrauss_min_dim(len(data), eps=epsilon)
                    # Log the layer, epsilon, dataset size, and minimum embedding dimension
                    print(f"Layer {layer}, epsilon {epsilon}: Dataset size is {len(data)}, Minimum embedding dimension suggested is {min_dim}")
                    output_file.write(f"Layer {layer}, epsilon {epsilon}: Dataset size is {len(data)}, Minimum embedding dimension suggested is {min_dim}\n")
                output_file.write("\n")

    

    def classifier_battery(self, embedded_data_dict: Dict[int, np.ndarray], labels: List[str], prompts: List[str], 
                           test_size: float = 0.2) -> None:
        """
        Runs a battery of classifiers on the given dataset, generating performance metrics and decision boundary plots.

        Parameters
        ----------
        embedded_data_dict: Dict[int, np.ndarray]
            Dict of layer-indexed feature data.
        labels: List[str]
            List of labels corresponding to the data.
        prompts: List[str]
            List of prompts associated with the data.
        test_size: float
            Proportion of the dataset to include in the test split.

        Returns:
        --------
        None

        Outputs:
        --------
        Saves classifier performance metrics and decision boundary plots for each layer.
        """
        classifiers = {
            "logistic_regression": LogisticRegression(),
            "decision_tree": DecisionTreeClassifier(),
            "random_forest": RandomForestClassifier(),
            "svc": SVC(probability=True),
            "knn": KNeighborsClassifier(),
            "gradient_boosting": GradientBoostingClassifier()
        }

        for clf_name, clf in classifiers.items():
            logging.info(f"Evaluating {clf_name}")
            metrics_dict = self.evaluate_classifiers(clf, embedded_data_dict, labels, prompts, test_size, clf_name)
            metrics_df = pd.DataFrame(metrics_dict)
            metrics_df.to_csv(f"{self.metrics_dir}/metrics_{clf_name}.csv", index=False)



    def evaluate_classifiers(self, clf: BaseEstimator, embedded_data_dict: Dict[int, np.ndarray], 
                             labels: List[str], prompts: List[str],test_size: float, clf_name: str) -> Dict[str, List[Any]]:
        """
        The function iterates over each layer in the embedded_data_dict, splits the data into 
        training and testing sets, fits the classifier, makes predictions, and calculates 
        the specified metrics. Decision boundary plots are generated and saved for each layer
        by calling plot_decision_boundary.

        Parameters:
        -----------
        clf: BaseEstimator
            The classifier to be evaluated.
        embedded_data_dict: Dict[int, np.ndarray]
            A dictionary where keys are layer indices and values are the embedded data points
            (np.ndarray) for each layer.
        labels: List[str]
            The ground truth labels for the data points.
        prompts: List[str]
            List of prompts associated with the data.
        test_size: float
            The proportion of the data to be used as the test set.
        clf_name: str
            The name of the classifier, used for labeling outputs.
        
        Reuturns:
        ---------
        Dict[str, List[Any]]
            A dictionary containing lists of metrics (accuracy, precision, recall, F1 score) for

        Notes:
        ------
        This function and those it calls work with the first two dimensions of the embedded data
        but they could work with larger numbers of dimensions if the embedded data has more than 2.
        It's just that it would only look at the first two dimensions for the decision boundary plots.
        """
        metrics_dict = {"Layer": [], "Accuracy": [], "Precision": [], "Recall": [], "F1 Score": []}
        for layer, representations in embedded_data_dict.items():
            X_train, X_test, y_train, y_test = train_test_split(representations, labels, test_size=test_size, random_state=self.seed)
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)

            metrics_dict["Layer"].append(layer)
            metrics_dict["Accuracy"].append(accuracy_score(y_test, y_pred))
            metrics_dict["Precision"].append(precision_score(y_test, y_pred, average='weighted', zero_division=0))
            metrics_dict["Recall"].append(recall_score(y_test, y_pred, average='weighted', zero_division=0))
            metrics_dict["F1 Score"].append(f1_score(y_test, y_pred, average='weighted', zero_division=0))

            self.plot_decision_boundary(clf, representations, labels, prompts, layer, clf_name)
        return metrics_dict
    


    def plot_decision_boundary(self, clf: BaseEstimator, representations: np.ndarray, labels: List[str], 
                               prompts: List[str], layer: int, clf_name: str) -> None:
        """
        Plots the decision boundary of a classifier and the data points using both
        Matplotlib and Plotly for a given layer's representations.

        Parameters:
        -----------
        clf: BaseEstimator
            The trained classifier (must have a `predict` or `predict_proba` method).
        representations: np.ndarray
            The 2D data points for plotting.
        labels: List[str]
            The actual labels for each data point.
        prompts: List[str]
            Text descriptions or prompts associated with each data point.
        layer: int
            The specific layer number being visualized.
        clf_name: str
            The name of the classifier, used for titling the plots.
        
        Returns:
        --------
        None

        Outputs:
        --------
        This function generates two files per layer:
        - A PNG image using Matplotlib.
        - An HTML file using Plotly for interactive visualization.

        Notes:
        ------
        Uses the entire dataset (representations), not just the test set
        to to be able to look at all the data (prompts) to get a sense of
        which ones are being classified incorrectly with this boundary.
        Why is this ok to do? Because the point of the classifier is not to make predicitons
        but to see if the representations can be used to classify the ethical area.
        """
        # Define the meshgrid for the contour plot
        x_min, x_max = representations[:, 0].min() - 1, representations[:, 0].max() + 1
        y_min, y_max = representations[:, 1].min() - 1, representations[:, 1].max() + 1
        xx, yy = np.meshgrid(np.arange(x_min, x_max, 0.1),
                             np.arange(y_min, y_max, 0.1))

        # Predict class or probabilities for the meshgrid
        if hasattr(clf, "predict_proba"):
            Z = clf.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, 1]
        else:
            Z = clf.predict(np.c_[xx.ravel(), yy.ravel()])
        Z = Z.reshape(xx.shape)

        # Define color mapping
        color_map = {'Bad False': 'red', 'Good True': 'green'}
        colors = [color_map.get(label, 'blue') for label in labels]  # Fallback color
        hover_text = [f'Prompt: {prompt}<br>Label: {label}' for prompt, label in zip(prompts, labels)]

        fig = go.Figure(data=[
            go.Contour(x=xx[0], y=yy[:, 0], z=Z, contours=dict(start=0.5, end=0.5, size=1), 
                       line_width=2, showscale=False),
            go.Scatter(x=representations[:, 0], y=representations[:, 1], mode='markers',
                       marker=dict(size=8, color=colors), text=hover_text, hoverinfo='text')
        ])
        fig.update_layout(title=f'Decision boundary for {clf_name} - Layer {layer}',
                          xaxis_title='Feature 1', yaxis_title='Feature 2')
        

        # Plots relating to metrics are saved in the metrics directory
        # but maybe they should be saved in the images directory?
        pio.write_html(fig, f"{self.metrics_dir}/decision_boundary_{clf_name}_{layer}.html")
        fig.write_image(f"{self.metrics_dir}/decision_boundary_{clf_name}_{layer}.png")




    #################################################
    # NON-DIMINSIONALITY REDUCTION ANALYSIS METHODS #
    #################################################

    def raster_plot(self, activations_cache: list[Activation],
                    compression: int=5) -> None:
        """
        Generates and saves raster plots for neural activations across different layers.
        Raster Plot has columns = Neurons and rows = Prompts. One chart for each layer

        Each raster plot visualizes the activations of neurons (columns) in response to 
        various prompts (rows) for a specific layer. The function iterates through each 
        layer in the activations cache, creating a chart that displays the neuron 
        activations for all prompts. The plots are saved as SVG files.

        Parameters
        ----------
        activations_cache : list[Activation]
            A list of `Activation` objects, each containing the hidden states for each 
            layer of a model and associated metadata, such as the prompts. It is assumed 
            that all `Activation` objects contain the same number of layers and neuron 
            activations.
        compression : int, optional
            A factor used to adjust the plot size and font scaling. Higher values compress 
            the plot and font size for a more condensed visualization. Default is 5.

        Returns
        -------
        None

        Outputs
        -------
        Saves SVG files of the raster plots.
        """
        # Using activations_cache[0] is arbitrary as they all have the same number of layers
        for layer in range(len(activations_cache[0].hidden_states)):
            
            data = np.stack([act.hidden_states[layer] for act in activations_cache])
            
            # Set the font size for the plot
            plt.rcParams.update({'font.size': (15 / compression)})

            neurons = activations_cache[0].hidden_states[0].size
            # Create the raster plot
            plt.figure(figsize=((neurons / (16 * compression)),
                                (len(activations_cache) + 2) / (2 * compression)))
            plt.imshow(data, cmap='hot', aspect='auto', interpolation="nearest")
            plt.colorbar(label='Activation')

            plt.xlabel('Neuron')
            plt.ylabel('Prompts')
            plt.title(f'Raster Plot of Neural Activations Layer {layer}')

            # Add Y-tick labels of the prompt
            plt.yticks(range(len(activations_cache)),
                    [activation.prompt for activation in activations_cache],
                    wrap=True)

            plot_path = os.path.join(self.images_dir, f"raster_plot_layer_{layer}.svg")
            print(plot_path)
            plt.savefig(plot_path)

            plt.close()



    def probe_hidden_states(self, activations_cache: list[Activation]) -> None:
        """
        Probes the hidden states of each layer using a decision tree classifier to predict
        the ethical area and positivity based on neuron activations, and visualizes the 
        decision tree.

        For each layer, this function splits the hidden states data into training and testing 
        sets, fits a decision tree classifier to predict the ethical area and positivity flag, 
        and then generates a classification report. It also creates a visualization of the 
        trained decision tree, saving the visualization as a PNG file for each layer.

        Parameters
        ----------
        activations_cache : list[Activation]
            A list of `Activation` objects, each containing the hidden states for each layer 
            of a model and associated metadata, such as the prompts, ethical area, and 
            positivity flag.

        Returns
        -------
        None

        Outputs
        -------
        Saves PNG files of the decision tree visualizations.
        """
        for layer in range(len(activations_cache[0].hidden_states)):

            data = np.stack([act.hidden_states[layer] for act in activations_cache])
            labels = [f"{act.ethical_area} {act.positive}" for act in activations_cache]
            unique_labels = sorted(list(set(labels)))

            X_train, X_test, y_train, y_test = train_test_split(data, labels, random_state=self.seed)

            clf = DecisionTreeClassifier(random_state=self.seed)
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)

            # TODO: Would want to log to hydra if useful
            print("Classification Report:\n", classification_report(y_test, y_pred))

            # Visualize the decision tree
            plt.figure(figsize=(20, 10))
            tree.plot_tree(clf, filled=True, class_names=unique_labels)
            plt.title("Decision tree for probing task")

            plot_path = os.path.join(self.images_dir, f"decision_tree_probe_layer_{layer}.png")
            plt.savefig(plot_path)
            plt.close()