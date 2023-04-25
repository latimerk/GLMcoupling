

# GLM with stimulus + coupling terms
# coupling terms are placed within a GLM for different types of regularization tests
class GLPPM:
    """
    A basic implementation of the Generalized linear point-process model for spike trains.
    The model has a stimulus input and possible "coupling" inputs, which are other spike trains from other neurons.
    Different attempts at correcting for the coupling inputs and regularization can be selected for.
    """
    def __init__(self, binSize_ms : float)