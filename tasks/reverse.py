from __future__ import division

import random

import torch
import torch.nn as nn
from torch.autograd import Variable

from tasks.base import Task, FormalTask
from models import VanillaModel
from controllers.feedforward import LinearSimpleStructController
from stacknn_utils import overrides
from structs import Stack


class ReverseTask(FormalTask):
    """String reversal task."""

    class Params(FormalTask.Params):

        def __init__(self, **kwargs):
            self.min_length = kwargs.get("min_length", 1)
            self.max_length = kwargs.get("max_length", 12)
            self.mean_length = kwargs.get("mean_length", 10)
            self.std_length = kwargs.get("std_length", 2.)
            self.num_symbols = kwargs.get("num_symbols", 2)
            super(ReverseTask.Params, self).__init__(**kwargs)

            # Override parameters from more abstract tasks.
            self.null = unicode(self.num_symbols)
            self.max_x_length = self.max_length * 2
            self.max_y_length = self.max_length * 8

    @property
    def input_size(self):
        return self.alphabet_size

    @property
    def output_size(self):
        return self.alphabet_size

    def _init_alphabet(self, null):
        return {unicode(i): i for i in xrange(self.num_symbols + 1)}

    """ Model Training """

    @overrides(Task)
    def _evaluate_step(self, x, y, a, j):
        """
        Computes the loss, number of guesses correct, and total number
        of guesses at the jth time step. The loss for a string is
        considered to be 0 if the neural network is still reading the
        input string.

        :type x: Variable
        :param x: The input data, represented as a 3D tensor. Each
            example consists of a string of 0s and 1s, followed by
            "null"s. All symbols are in one-hot representation

        :type y: Variable
        :param y: The output data, represented as a 2D tensor. Each
            example consists of a sequence of "null"s, followed by a
            string backwards. All symbols are represented numerically

        :type a: Variable
        :param a: The output of the neural network at the jth time step,
            represented as a 2D vector. For each i, a[i, :] is the
            output of the neural network at the jth time step, in one-
            hot representation

        :type j: int
        :param j: This function is called during the jth time step of
            the neural network's computation

        :rtype: tuple
        :return: The loss, number of correct guesses, and number of
            total guesses at the jth time step
        """
        indices = (y[:, j] != self.alphabet[self.null])
        # Indexing semantics in the line below were changed in different versions of pytorch.
        valid_a = a[indices.view(-1)].view(-1, self.alphabet_size)
        valid_y = y[:, j][indices]

        if len(valid_a) == 0:
            return None, None, None

        _, valid_y_ = torch.max(valid_a, 1)

        total = len(valid_a)
        correct = len(torch.nonzero((valid_y_ == valid_y).data))
        loss = self.criterion(valid_a, valid_y)
        return loss, correct, total

    """ Data Generation """

    def get_data(self):
        """
        Generates training and testing datasets for this task using the
        self.get_tensors method.

        :return: None
        """
        self.train_x, self.train_y = self.get_tensors(800)
        self.test_x, self.test_y = self.get_tensors(100)

    def randstr(self):
        """
        Generates a random string over self.alphabet, not including
        NULLs. The lengths of the strings generated by this function
        have a Gaussian distribution with the following properties.
            Minimum Length: self.min_length
            Maximum Length: self.max_length
            Average Length: self.mean_length
            Standard Deviation: self.std_length

        :rtype: list
        :return: A sequence of "0"s and "1"s
        """
        length = int(random.gauss(self.mean_length, self.std_length))
        length = min(max(self.min_length, length), self.max_length)
        s = [random.randint(0, self.num_symbols - 1) for _ in xrange(length)]
        return [unicode(w) for w in s]

    def get_tensors(self, num_tensors):
        """
        Generates a dataset containing correct input and output values
        for the reversal task. An input value is a sequence of n-many
        symbols for some n. An output value is a sequence of n-many
        NULLs, followed by the input value backwards. Input and output
        values are padded to their maximum lengths with NULLs.

        For example, the following is a valid input-output pair,
        assuming that u"2" is the null symbol.
            Input: [u"1", u"0", u"2", u"2"]
            Output: [u"2", u"2", u"0", u"1"]

        :type num_tensors: int
        :param num_tensors: The number of examples in the dataset

        :rtype: tuple
        :return: A Variable containing the input values and a Variable
            containing the output values
        """
        x_raw = [self.randstr() for _ in xrange(num_tensors)]
        y_raw = [[self.null for _ in xrange(len(s))] + s[::-1] for s in x_raw]

        x_var = self.sentences_to_one_hot(self.max_x_length, *x_raw)
        y_var = self.sentences_to_codes(self.max_y_length, *y_raw)

        return x_var, y_var

    @property
    def generic_example(self):
        """The string for visualizations."""
        return [u'1', u'1', u'1', u'2', u'1', u'1', u'2', u'1', u'1', u'2', u'1', u'2', u'2', u'1', u'2', u'2', u'2',
                u'2', u'2', u'1', u'0', u'0', u'0', u'0', u'0', u'0', u'0', u'0', u'0', u'0', u'0', u'0', u'0', u'0',
                u'0', u'0', u'0', u'0', u'0', u'0']


class CopyTask(ReverseTask):
    """
    String Copying
    """

    def get_tensors(self, num_tensors):
        """
        Generates a dataset containing correct input and output values
        for the copy task. The input and output values are identical.

        :type num_tensors: int
        :param num_tensors: The number of examples in the dataset

        :rtype: tuple
        :return: A Variable containing the input values and a Variable
            containing the output values
        """
        x_raw = [self.randstr() for _ in xrange(num_tensors)]

        x_var = self.sentences_to_one_hot(2 * self.max_length, *x_raw)
        y_var = self.sentences_to_codes(2 * self.max_length, *x_raw)

        return x_var, y_var


class ReverseDeletionTask(ReverseTask):
    """
    Reverse the result of deleting the second half of the
    alphabet symbols from the input string.
    Example: 12200313011 => 1101001  over the alphabet {0,1,2,3}
    """

    def get_tensors(self, num_tensors):
        """
        Generates a dataset containing correct input and output values
        for the reverse deletion task.

        :type num_tensors: int
        :param num_tensors: The number of examples in the dataset

        :rtype: tuple
        :return: A Variable containing the input values and a Variable
            containing the output values
        """
        x_raw = [self.randstr() for _ in xrange(num_tensors)]
        y_raw = [[self.null for _ in xrange(len(s))] + self.reverse_with_delete(s) for s in x_raw]

        x_var = self.sentences_to_one_hot(self.max_x_length, *x_raw)
        y_var = self.sentences_to_codes(self.max_y_length, *y_raw)

        return x_var, y_var

    def reverse_with_delete(self, s):
        large_symbol = self.num_symbols // 2
        t = []
        for symbol in s:
            if int(symbol) < large_symbol:
                t.append(symbol)
        return t[::-1]
