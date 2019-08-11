import torch
import torch.autograd as autograd
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim


# TODO might want to swap dimensions on V for consistency

class Stack(nn.Module):
    """
    Neural stack implementation based on Grefenstette et al., 2015.
    @see https://arxiv.org/pdf/1506.02516.pdf
    """

    def __init__(self, batch_size, embedding_size, k=None):
        super(Stack, self).__init__()

        # initialize tensors
        self.V = Variable(torch.FloatTensor(0))
        self.s = Variable(torch.FloatTensor(0))

        # controls number of read vectors
        self.k = k

        self.zero = Variable(torch.zeros(batch_size))

        self.batch_size = batch_size
        self.embedding_size = embedding_size

    def forward(self, v, u, d):
        """
        @param v [batch_size, embedding_size] matrix to push
        @param u [batch_size,] vector of pop signals in (0, 1)
        @param d [batch_size,] vector of push signals in (0, 1)
        @return [batch_size, embedding_size] or [batch_size, self.k, embedding_size] read matrix
        """

        # update V, which is of size [t, bach_size, embedding_size]
        v = v.view(1, self.batch_size, self.embedding_size)
        self.V = torch.cat([self.V, v], 0) if len(self.V.data) != 0 else v

        # TODO append to self.s so we can terminate lower loop early?
        # TODO initialize stack to fixed size

        # update s, which is of size [t, batch_size]
        old_t = self.s.data.shape[0] if self.s.data.shape else 0
        s = Variable(torch.FloatTensor(old_t + 1, self.batch_size))
        w = u
        for i in reversed(xrange(old_t)):
            s_ = F.relu(self.s[i, :] - w)
            w = F.relu(w - self.s[i, :])
            s[i, :] = s_
        s[old_t, :] = d
        self.s = s

        if self.k is None:

            # calculate r, which is of size [batch_size, embedding_size]
            r = Variable(torch.zeros([self.batch_size, self.embedding_size]))
            for i in reversed(xrange(old_t + 1)):
                used = torch.sum(self.s[i + 1:old_t + 1, :], 0) if i < old_t else self.zero
                coeffs = torch.min(self.s[i, :], F.relu(1 - used))
                # reformating coeffs into a matrix that can be multiplied element-wise
                r += coeffs.view(self.batch_size, 1).repeat(1, self.embedding_size) * self.V[i, :, :]
            return r

        else:  # calculate k read vectors

            # TODO can probably make this more efficient

            r = Variable(torch.zeros([self.batch_size, self.k, self.embedding_size]))
            for k in xrange(self.k):
                for i in reversed(xrange(old_t + 1)):
                    used = torch.sum(self.s[i + 1:old_t + 1, :], 0) if i < old_t else self.zero
                    coeffs = torch.min(self.s[i, :], F.relu(1 + k - used))
                    r[:, k, :] = r[:, k, :] + coeffs.view(self.batch_size, 1).repeat(1, self.embedding_size) * self.V[i,
                                                                                                               :, :]
            for k in reversed(xrange(1, self.k)):
                r[:, k, :] = r[:, k, :] - r[:, k - 1, :]
            return r

    def log(self):
        """
        Prints a representation of the stack to stdout.
        """
        V = self.V.data
        if not V.shape:
            print "[Empty stack]"
            return
        for b in xrange(self.batch_size):
            if b > 0:
                print "----------------------------"
            for i in xrange(V.shape[0]):
                print "{}\t|\t{:.2f}".format("\t".join("{:.2f}".format(x) for x in V[i, b, :]), self.s[i, b].data[0])


if __name__ == "__main__":
    print "Simulating example stack.."
    stack = Stack(1, 1)
    stack.log()
    out = stack.forward(
        Variable(torch.FloatTensor([[1]])),
        Variable(torch.FloatTensor([[0]])),
        Variable(torch.FloatTensor([[.8]])),
    )
    print "\n\n"
    stack.log()
    print "read", out
    out = stack.forward(
        Variable(torch.FloatTensor([[2]])),
        Variable(torch.FloatTensor([[.1]])),
        Variable(torch.FloatTensor([[.5]])),
    )
    print "\n\n"
    stack.log()
    print "read", out
    out = stack.forward(
        Variable(torch.FloatTensor([[3]])),
        Variable(torch.FloatTensor([[.9]])),
        Variable(torch.FloatTensor([[.9]])),
    )
    print "\n\n"
    stack.log()
    print "read", out
