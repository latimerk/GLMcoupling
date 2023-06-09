import numpy as np
from scipy.linalg import orth
from abc import ABC
from scipy.signal import convolve2d

def fix_window(bin_size_ms : float,window : tuple[float,float], floor_start : bool = True, binned_times : bool = False):
    assert len(window) == 2, "window must have two elements"
    window_0 = window[0]
    if(floor_start):
        window_0 -= (window[0] % bin_size_ms);
    T_bins = np.floor((window[1] - window_0) / bin_size_ms).astype(int);
    assert T_bins > 0, "window must contain at least one timebin"

    window_0_bins = np.floor(window_0 / bin_size_ms).astype(int);
    window_bins = (window_0_bins, window_0_bins + T_bins);
    window_rounded = (window_0, window_0 + T_bins * bin_size_ms);
    if binned_times:
        tts = np.arange(window_bins[0], window_bins[1]);
    else:
        tts = np.arange(window_rounded[0], window_rounded[1], bin_size_ms);
    return (T_bins, window_rounded, tts,window_bins);



# basis function builder
class BasisSet(ABC):   
    """
    Abstract base class to hold basis functions for analyzing neural data.
    The basis sets here will work with binned time data (with all equal bins)
    """
    def _do_convolution(self,yy,T_bins):

        # do convolution
        X_0 = convolve2d(yy[:,np.newaxis], self.B, mode='full');

        # trim convolution
        t_0   = self._first_offset; # first valid element
        t_end = t_0 + T_bins;
            # check for beyond boundary conditions
        if(t_0 < 0 or t_end > X_0.shape[0]):
            X = np.zeros((T_bins, X_0.shape[1]));

            t_1 = np.maximum(-t_0, 0)
            t_0x  = t_1;
            t_0  += t_1;

            t_1    = np.maximum(t_end - X_0.shape[0], 0);
            t_endx  = T_bins - t_1;
            t_end  -= t_1;

            X[t_0x:t_endx,:] = X_0[t_0:t_end, :];
        else:
            X = X_0[t_0:t_end, :];

        return X;

    def convolve_continuous_event(self, Stim : np.array, window : tuple[float,float], floor_start : bool = True) -> tuple[np.ndarray,np.ndarray,tuple[int,int]]:
        """
        Convolves the basis with a continuous (1-D only) signal for building a design matrix.

        Args
          Stim: an array containing the stimulus values over time (binned time - does not covert frames/seconds to bins)
          window: (start, end) first and last (exclusive) time points of the convolution in ms
          floor_start: if True, makes the window start equal to a multiple of :attr:`bin_size_ms`.

        Returns:
          (X, tts, window_rounded, window_bins) : X (np.ndarray) [T x P], basis convolved by time
                        tts (np.ndarray) [T] - time points of rows of X in ms
                        window_rounded (tuple[int,int]) - the time bins in ms
                        window_bins (tuple[int,int]) - the binned time
        """
        
        (T_bins, window_rounded, tts, window_bins) = fix_window(self.bin_size_ms, window, floor_start)

        assert Stim.ndim == 1, "Stim must be one dimensional array"
        window_conv = (window_bins[0] -  self._first_offset + self._last_offset, window_bins[1] + self._last_offset);
        assert window_conv[0] >= 0, "Window invalid for given basis length: does not auto-pad with zeros"
        assert len(Stim) > window_conv[1], "Stim must be at least length " + str(window_conv[1]) + ", received length " + str(len(Stim))

        Stim_0 = Stim[window_conv[0]:window_conv[1]]

        X = self._do_convolution(Stim_0,T_bins);

        return (X, tts,  window_rounded, window_bins);


    def convolve_point_events(self, times : list, window : tuple[float,float], floor_start : bool = True, binned_events : bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int,int]]:
        """
        Convolves the basis with a set of times for building a design matrix.

        Args
          times: a list of event times in ms (or bins if binned_events == True)
          window: (start, end) first and last (exclusive) time points of the convolution in ms
          floor_start: if True, makes the window start equal to a multiple of :attr:`bin_size_ms`.
          binned_events: whether the times are in bins (True) or ms (False)

        Returns:
          (X, tts,  window_rounded) : X (np.ndarray) [T x P], basis convolved by time
                        tts (np.ndarray) [T] - time points of rows of X in ms
                        window_rounded (tuple[int,int]) - the time bins in ms
                        window_bins (tuple[int,int]) - the time bins

        """
        
        (T_bins, window_rounded, tts, window_bins) = fix_window(self.bin_size_ms, window, floor_start);

        if binned_events:
            window_conv = (window_bins[0] -  self._first_offset + self._last_offset, window_bins[1] + self._last_offset);
            tts_padded = np.arange(window_conv[0] - (self._first_offset - self._last_offset), window_conv[1]);
        else:
            tts_padded = np.arange(window_rounded[0] - (self._first_offset - self._last_offset)*self.bin_size_ms, window_rounded[1],self.bin_size_ms);

        yy , *_ = np.histogram(times, tts_padded);

        # do convolution
        X = self._do_convolution(yy,T_bins);

        return (X, tts, window_rounded, window_bins);


    def get_row_indices_for_point_events(self, event_times : list, window : tuple[float,float], set_invalid_to_none : bool = False, floor_start : bool = False) -> tuple[np.ndarray,np.ndarray]:
        """
        Gets the indices into the rows of the basis function for all times in a window for a set of point events.

        Args
          event_times: [A] a list of event times in ms
          window: (start, end) first and last (exclusive) time points of the convolution in ms
          set_invalid_to_none: if True, any invalid rows set to None, otherwise allows negative and too-large indices.
          floor_start: if True, makes the window start equal to a multiple of :attr:`bin_size_ms`.

        Returns:
          (X, tts) : X (np.ndarray) [T x A], row index of into basis for each event. These indices may be invalid (negative or too large) if set_invalid_to_none==False, otherwise invalid indices are None. 
                     tts (np.ndarray) [T] - time points of rows of X in ms

        """
        (T_bins, window_rounded, tts, window_bins) = fix_window(self.bin_size_ms, window, floor_start)
        event_times = np.array(event_times);
        
        X_0 = tts.reshape((tts.size, 1)) - event_times.reshape((1, event_times.size));
        X = np.floor(X_0 / self.bin_size_ms);

        if(set_invalid_to_none):
            X[X < 0] = np.nan;
            X[X >= self.B.shape[0]] = np.nan;

        return (X, tts);

    @property
    def _first_offset(self) -> int:
        assert hasattr(self, '_B'), "Basis not initialized!"
        return -np.floor(self.T[0]/self.bin_size_ms).astype(int) + (self.B.shape[0])

    @property
    def _last_offset(self) -> int:
        assert hasattr(self, '_B'), "Basis not initialized!"
        return self._first_offset - self.B.shape[0]

    @property
    def BT(self) -> int:
        """
        length of the basis functions
        """
        assert hasattr(self, '_B'), "Basis not initialized!"
        return self._B.shape[0]

        
    @property
    def P(self) -> int:
        """
        number of basis functions
        """
        assert hasattr(self, '_B'), "Basis not initialized!"
        return self._B.shape[1]

    @property
    def B(self) -> np.ndarray:
        """
        ndarray [BT x P] : the basis set (each basis is in a column)
        """
        assert hasattr(self, '_B'), "Basis not initialized!"
        return self._B

        
    @property
    def B_0(self) -> np.ndarray:
        """
        ndarray [BT x P] : the basis set (each basis is in a column)
        """
        assert hasattr(self, '_B') or hasattr(self, '_B_0'), "Basis not initialized!"
        if(hasattr(self,"_B_0")):
            return self._B_0
        else:
            return self.B

    @property
    def T(self) -> np.ndarray:
        """
        ndarray [BT] : the time points of each basis function
        """
        assert hasattr(self, '_T'), "Basis not initialized!"
        return self._T

    @property
    def bin_size_ms(self) -> np.ndarray:
        """
        float : the bin size of the basis in ms
        """
        assert hasattr(self, '_bin_size_ms'), "Basis not initialized!"
        return self._bin_size_ms
        
    @property
    def orthogonalized(self) -> bool:
        """
        Whether or not basis set was orthogonalized.
        """
        if(hasattr(self, '_orthogonalized')):
            return self._orthogonalized
        else:
            return False

    @orthogonalized.setter
    def orthogonalized(self, val):
        assert type(val) == bool, f"orthonalized must be a boolean"
        self._orthogonalized = val;
        self._reset();

    @property
    def rescale_goal(self) -> float:
        """
        Rescaling parameter for more consistent regularization. If is None, no rescaling occurs.
        """
        if(hasattr(self, '_rescale_goal')):
            return self._rescale_goal
        else:
            return None

    @rescale_goal.setter
    def rescale_goal(self, val):
        assert (type(val) in [float,int] and val > 0) or (val is None), f"rescale goal must be a positive number or None"
        self._rescale_goal = val;
        self._reset();

    def _reset(self):
        """
        Internal method for orthogonalizing and rescaling the basis.
        """
        self._orthognalize();
        self._rescale();

    def _orthognalize(self):
        """
        Internal method for orthogonalizing the basis.
        """
        if(self._orthogonalized):
            # makes the basis orthonormal
            self._B = orth(self._B_0);
        else:
            self._B = self._B_0.copy();

    def _rescale(self):
        """
        Internal method for rescaling the basis according to rescale_goal.
        """
        if(not self.rescale_goal is None):
            # rescales the basis for priors on the tensor regression
            # so that the expected STD over time of a filtered impulse (under unit normal coefs) goes to 1
            #cale_resp  = np.trace(self.B.T @ self.B)/self.B.shape[0] - (self.B.sum(axis=0)**2).sum()/self.B.shape[0]**2;
            #scale_resp  = np.sqrt(scale_resp); # variance -> std
            self._rescale_const  = self.rescale_goal * np.sqrt(np.trace(np.cov(self.B,rowvar=False)));
            # scale_resp *= self.rescale_goal * np.sqrt(2/np.pi); #multiplies by E(abs(Normal(0,1))) (for the other components)
            
            self.B /=  self._rescale_const;
        else:
            self._rescale_const = None;

class ModifiedCardinalSpline(BasisSet):
    """
    Holds a Modified Cardinal Spline basis function set.
    The bases are given as in proposed Sarmashghi, M., Jadhav, S. P., & Eden, U. (2021). Efficient Spline Regression for Neural Spiking Data. bioRxiv.

    Modified by Kenneth Latimer from Repository:
        https://github.com/MehradSm/Modified-Spline-Regression
        by Mehrad Sarmashghi
    """
    def __init__(self, window, c_pt : list[float], s : float = 0.5, bin_size_ms : float = 1, zero_first : bool = False, zero_last : bool = False, rescale_goal : float = None, orthogonalize : bool = True) -> tuple[np.ndarray, np.ndarray]:
        """
        Args:
        window:         tuple (float, float): first and last time points of the window in ms
                        if scalar, sets to (bin_size_ms, window) 
        c_pt:           Locations of the knots.
        s:              Tension parameter
        bin_size_ms:    Time bin size in milliseconds
        zero_first:     Whether to set the end point at c_pt[0 ] to 0's (removes basis)
        zero_last:      Whether to set the end point at c_pt[-1] to 0's (removes basis)
        orthogonalize:  To orthogonalize the basis or not
        rescale_goal:   A scaling parameter for the basis functions by a constant for shrinkage priors (if None, does not rescale)
        """
        assert bin_size_ms > 0, f"bin size must be positive"
        self._bin_size_ms = bin_size_ms;
        assert (type(window) == tuple and len(window) == 2) or (type(window) in [float,int]), f"window should be a tuple defining the time window of the filter."
        if len(window) == 1:
            window = (bin_size_ms, window);

        self._window = window;
        self._T  = np.arange(self._window[0], self._window[1], self._bin_size_ms);
        dim_T    = self._T.size;

        assert len(c_pt) >= 4, f"Need at least 4 knot points greater than 0 expected, got: {len(c_pt)}"
        assert dim_T > 0, f"Basis window is empty"

        self._tension = s;
        c_pt.sort();
        self._c_pt = np.array(c_pt);  
        

        HistSpl = np.zeros((dim_T,len(self._c_pt)));

        # for each 1 ms timepoint, calculate the corresponding row of the glm input matrix
        for tt_idx, tt in enumerate(self._T):
            nearest_c_pt_index = np.where(self._c_pt < tt)[0];
            assert len(nearest_c_pt_index) > 0, f"Cannot find knot index for all points in window {tt} {tt_idx}"
            nearest_c_pt_index = nearest_c_pt_index[-1];
            nearest_c_pt_time  = self._c_pt[nearest_c_pt_index];
            next_c_pt_time     = self._c_pt[nearest_c_pt_index+1];
            
            # Compute the fractional distance between timepoint i and the nearest knot
            u  = (tt - nearest_c_pt_time)/(next_c_pt_time - nearest_c_pt_time);
            lb = (self._c_pt[ 2]   - self._c_pt[ 0])/(self._c_pt[1]   - self._c_pt[0]);
            le = (self._c_pt[-2] - self._c_pt[-3])/(self._c_pt[-1] - self._c_pt[-2]);
            
            # Beginning knot 
            if(nearest_c_pt_time == self._c_pt[0]):
                S = np.array([[2-(s/lb), -2, s/lb], \
                    [(s/lb)-3,  3, -s/lb], \
                        [0,  0,  0], \
                            [1,  0,  0]]);
                bbs = range(nearest_c_pt_index, nearest_c_pt_index+3);
                
            # End knot
            elif(nearest_c_pt_time == self._c_pt[-2]):
                S = np.array([[-s/le,  2, -2+(s/le)], \
                    [2*s/le, -3, 3-(2*s/le)], \
                        [-s/le, 0, s/le], \
                            [0, 1, 0]]);
                bbs = range(nearest_c_pt_index-1, nearest_c_pt_index+2);
                
            # Interior knots
            else:
                privious_c_pt = self._c_pt[nearest_c_pt_index-1];
                next2 = self._c_pt[nearest_c_pt_index+2];
                l1 = next_c_pt_time - privious_c_pt;
                l2 = next2 - nearest_c_pt_time;
                S = np.array([[ -s/l1, 2-(s/l2), (s/l1)-2, s/l2], \
                    [2*s/l1, (s/l2)-3, 3-2*(s/l1), -s/l2], \
                        [-s/l1, 0, s/l1, 0], \
                            [0, 1, 0, 0]]);
                bbs = range(nearest_c_pt_index-1, nearest_c_pt_index+3);

            p = np.array([[u**3, u**2, u, 1]]) @ S;
            HistSpl[tt_idx, bbs] = p; 

        assert not np.isnan(HistSpl).any() and not np.isinf(HistSpl).any(), f"basis error: cannot contain infs or nans"

        if zero_first:
            HistSpl = HistSpl[:, 1:];
        if zero_last:
            HistSpl = HistSpl[:, :-1];

        self._zero_first = zero_first;
        self._zero_last  = zero_last;
        self._B_0 = HistSpl.copy();
        self._B = HistSpl;

        self.orthogonalized = orthogonalize;
        self.rescale_goal = rescale_goal;
        self._rescale_const = None;
        self._reset();
        
    @property
    def zero_first(self) -> bool:
        """
        Whether or not first basis function was removed/zeroed out.
        """
        return self._zero_first
        
    @property
    def zero_last(self) -> bool:
        """
        Whether or not last basis function was removed/zeroed out.
        """
        return self._zero_last

        
    @property
    def window(self) -> tuple:
        """
        The window of the basis set: tuple (float, float) for the start & end
        """
        return self._window
        
    @property
    def tension(self) -> float:
        """
        The tension parameter of the basis.
        """
        return self._tension
        
    @property
    def knots(self) -> float:
        """
        The knot locations (in ms).
        """
        return self._c_pt


def getRGCStimBasis(bin_size_ms : float, orthogonalize : bool = True) -> tuple[np.ndarray, np.ndarray]:
    """
    A simple default basis to use for stimulus-dependent conductance filters made with a modified cardinal spline.

    Args:
      bin_size_ms: time bin size in milliseconds
      orthogonalize: return orthonormal basis if True, otherwise returns splines

    Returns:
      A ModifiedCardinalSpline containing the basis
    """
    return ModifiedCardinalSpline((bin_size_ms, 190), [0, 8, 16, 24, 32, 40, 48, 64, 96, 128, 160, 192], bin_size_ms=bin_size_ms, zero_last=False, zero_first=True, orthogonalize=orthogonalize);

def getRGCSpkHistBasis(bin_size_ms : float, orthogonalize : bool = True) -> tuple[np.ndarray, np.ndarray]:
    """
    A simple default basis to use for spike history filters made with a modified cardinal spline.

    Args:
      bin_size_ms: time bin size in milliseconds, otherwise returns splines

    Returns:
      A ModifiedCardinalSpline containing the basis
    """
    return ModifiedCardinalSpline((bin_size_ms, 190), [0, 1, 2, 4, 8, 16, 24, 32, 40, 48, 64, 96, 128, 160, 192], bin_size_ms=bin_size_ms, zero_last=False, zero_first=False, orthogonalize=orthogonalize);
    