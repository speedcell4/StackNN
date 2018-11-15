from __future__ import division
from __future__ import print_function

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable

from tasks.base import Task
from stacknn_utils.vector_ops import array_map
from stacknn_utils.testcase import testcase, test_module
from stacknn_utils import overrides


class NaturalTask(Task):

    """A task for loading and training on raw data; i.e. not generated data.

    It is assumed that the data is in CSV format. It is read into a pandas
    DataFrame and then used to train a model.
    """

    
    class Params(Task.Params):

        """New parameters for a task that loads a natural language dataset.

        See Task.Params for information about inherited parameters.

        Attributes:
            train_path: Path (from root directory of project) to a training
                file.
            test_path: Path (from root directory of project) to a test file.
            data_reader: Class specifying how to read the data from these files.
            max_num_embeddings: An upper bound on the number of words in the
                dataset.
            max_num_output_classes: An upper bound on the number of output
                classes in the dataset.
        """

        def __init__(self, train_path, test_path, data_reader, **kwargs):
            self.train_path = train_path
            self.test_path = test_path
            self.data_reader = data_reader
            self.max_num_embeddings = kwargs.get("max_num_embeddings", 5000)
            self.max_num_output_classes = kwargs.get("max_num_output_classes", 2)
            super(NaturalTask.Params, self).__init__(**kwargs)


    @property
    def input_size(self):
        return self.max_num_embeddings

    @property
    def output_size(self):
        return self.max_num_output_classes

    def get_data(self):
        self.data_reader.reset_counts()

        import os
        print(os.getcwd())

        train_x, train_y = self.data_reader.read_x_and_y(self.train_path)
        test_x, test_y = self.data_reader.read_x_and_y(self.test_path)

        max_length = self.data_reader.max_x_length
        pad = lambda line: np.pad(line, max_length, "constant")
        train_x = array_map(pad, train_x)
        test_x = array_map(pad, test_x)

        print(train_x)

    @overrides(Task)
    def _evaluate_step(self, x, y, a, j):
        pass
