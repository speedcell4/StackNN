"""
    Code for building language models from (P)CFGs
"""
from __future__ import division

import random
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.autograd import Variable
from sklearn.utils import shuffle
from nltk.parse.generate import generate
from nltk import CFG, PCFG
from itertools import izip

m = __import__("model-bare")

# Language parameters
DEPTH = 5
MIN_LENGTH = 2
STD_LENGTH = 2
MAX_LENGTH = 2 ** (DEPTH - 1)
MEAN_LENGTH = MAX_LENGTH / 2

# Hyperparameters
LEARNING_RATE = .01  # .01 and .1 seem to work well?
BATCH_SIZE = 10  # 10 is the best I've found
READ_SIZE = 2  # length of vectors on the stack

CUDA = False
EPOCHS = 30

grammar = PCFG.fromstring("""
S -> S S [0.2]
S -> '(' S ')' [0.2] | '(' ')' [0.2]
S -> '[' S ']' [0.2] | '[' ']' [0.2]
""")

# parenthesis_strings = list(generate(grammar, depth=3))
# was using this to set max depth ^
code_for = {u'(': 0, u')': 1, u'[': 2, u']': 3, '#': 4}

model = m.FFController(len(code_for), READ_SIZE, len(code_for))
if CUDA:
    model.cuda()

criterion = nn.CrossEntropyLoss()

def generate_sample(grammar, prod, frags):
    """
    Generate random sentence using PCFG.
    @see https://stackoverflow.com/questions/15009656/how-to-use-nltk-to-generate-sentences-from-an-induced-grammar
    """     
    if prod in grammar._lhs_index: # Derivation
        derivations = grammar._lhs_index[prod]            
        derivation = random.choice(derivations)            
        for d in derivation._rhs:            
            generate_sample(grammar, d, frags)
    elif prod in grammar._rhs_index:
        # terminal
        frags.append(str(prod))

def randstr():
    string = []
    generate_sample(grammar, grammar.start(), string)
    # string = random.choice(parenthesis_strings)
    return [code_for[s] for s in string]


reverse = lambda s: s[::-1]
onehot = lambda b: torch.FloatTensor([1. if i == b else 0. for i in xrange(len(code_for))])


def get_tensors(B):
    X_raw = [randstr() for _ in xrange(B)]

    # initialize X to one-hot encodings of NULL
    X = torch.FloatTensor(B, MAX_LENGTH, len(code_for))
    X[:, :, :len(code_for) - 1].fill_(0)
    X[:, :, len(code_for) - 1].fill_(1)

    # initialize Y to NULL
    Y = torch.LongTensor(B)
    Y.fill_(0)

    for i, x in enumerate(X_raw):
        length = min(max(MIN_LENGTH - 1, int(random.gauss(MEAN_LENGTH, STD_LENGTH))), len(x) - 1)
        for j, char in enumerate(x[:length]):
            X[i, j, :] = onehot(char)
        Y[i] = x[length]
    return Variable(X), Variable(Y)


train_X, train_Y = get_tensors(800)

# print train_X[0,0,:]
# print train_Y[0]

dev_X, dev_Y = get_tensors(100)
test_X, test_Y = get_tensors(100)


def train(train_X, train_Y):
    model.train()
    total_loss = 0.

    for batch, i in enumerate(xrange(0, len(train_X.data) - BATCH_SIZE, BATCH_SIZE)):

        X, Y = train_X[i:i + BATCH_SIZE, :, :], train_Y[i:i + BATCH_SIZE]
        model.init_stack(BATCH_SIZE)

        valid_X = (X[:, :, len(code_for) - 1] != 1)
        lengths_X = torch.sum(valid_X.type(torch.LongTensor), 1)
        A = Variable(torch.FloatTensor(BATCH_SIZE, MAX_LENGTH, len(code_for)))
        
        for j in xrange(MAX_LENGTH):
            a = model.forward(X[:, j, :])
            A[:, j, :] = a

        # see https://stackoverflow.com/questions/49104307/indexing-on-axis-by-list-in-pytorch
        predicted_Y = torch.stack([a[i] for a, i in izip(A, lengths_X)])
        predicted_Y = torch.squeeze(predicted_Y)

        batch_loss = criterion(predicted_Y, Y)
        _, predictions = torch.max(predicted_Y, 1)
        accuracy = sum((predictions == Y).data) / len(Y.data)

        # update the weights
        optimizer.zero_grad()
        batch_loss.backward()
        optimizer.step()

        total_loss += batch_loss.data
        if batch % 10 == 0:
            print "batch {}: loss={:.4f}, acc={:.2f}".format(batch, sum(batch_loss.data) / BATCH_SIZE, accuracy)


def evaluate(test_X, test_Y):
    model.eval()
    model.init_stack(len(test_X.data))

    valid_X = (test_X[:, :, len(code_for) - 1] != 1)
    lengths_X = torch.sum(valid_X.type(torch.LongTensor), 1)
    A = Variable(torch.FloatTensor(len(test_X.data), MAX_LENGTH, len(code_for)))
    
    for j in xrange(MAX_LENGTH):
        a = model.forward(test_X[:, j, :])
        A[:, j, :] = a

    # see https://stackoverflow.com/questions/49104307/indexing-on-axis-by-list-in-pytorch
    predicted_Y = torch.stack([a[i] for a, i in izip(A, lengths_X)])
    predicted_Y = torch.squeeze(predicted_Y)

    _, predictions = torch.max(predicted_Y, 1)
    accuracy = sum((predictions == test_Y).data) / len(test_Y.data)
    total_loss = criterion(predicted_Y, test_Y)

    # print model.state_dict()
    print "epoch {}: loss={:.4f}, acc={:.2f}".format(epoch, sum(total_loss.data) / len(test_X), accuracy)


# optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
print "hyperparameters: lr={}, batch_size={}, read_dim={}".format(LEARNING_RATE, BATCH_SIZE, READ_SIZE)
for epoch in xrange(EPOCHS):
    print "-- starting epoch {} --".format(epoch)
    perm = torch.randperm(800)
    train_X, train_Y = train_X[perm], train_Y[perm]
    train(train_X, train_Y)
    evaluate(dev_X, dev_Y)
