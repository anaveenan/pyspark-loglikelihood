# coding: utf-8
import math


def x_logx(x):
    if x <= 0:
        return 0.0
    return x * math.log(x)


def entropy_2(a, b):
    """Entropy(x,y)."""
    return x_logx(a + b) - x_logx(a) - x_logx(b)


def entropy_4(a, b, c, d):
    """Entropy optimization for 4 items."""
    return x_logx(a + b + c + d) \
        - x_logx(a) \
        - x_logx(b) \
        - x_logx(c) \
        - x_logx(d)


def loglikelihood(k11, k12, k21, k22):
    """Log LogLikelihood Formula."""
    row_entropy = entropy_2(k11 + k12, k21 + k22)
    column_entropy = entropy_2(k11 + k21, k12 + k22)
    matrix_entropy = entropy_4(k11, k12, k21, k22)

    if (row_entropy + column_entropy) < matrix_entropy:
        return 0.0
    return float(2.0 * (row_entropy + column_entropy - matrix_entropy))


def loglikelihood_ratio(k11, k12, k21, k22):
    """LLR = 1.0 - ( 1.0 / (1.0 + LLR) )."""
    return 1.0 - (1.0 / (1.0 + float(loglikelihood(k11, k12, k21, k22))))


__all__ = ['loglikelihood_ratio']
