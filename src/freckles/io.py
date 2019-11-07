from pathlib import Path
import h5py
import numpy as np
import healpy as hp

class IO(object):
    """ Class to handle input and output for a set of `freckles` simulations.

    This class provides methods to write to an h5 file.
    """
    def __init__(self, pathobj):
        try:
            assert isinstance(pathobj, Path)
        except AssertionError:
            raise("IO must be initialized with Path object")

        self.path = pathobj

class Input():
    
    def __init__(self):
        return

class HealpixInputs(object):

    def __init__(self, nside, nfreqs, npol, idx=None):
        """ Function to initialize `HealpixInputs`.

        This function will take the `iterator` input, which returns a set of
        file names. Each file is assumed to contain a set of IQU maps at `nside`
        resolution.

        Parameters
        ----------
        iterator: iterable
            Iterable that returns the files to be read in. These are expected to be
            in order of (IQU)_nu0, COV(IQU)_nu0, (IQU)_nu1, COV(IQU)_nu1 ...
        nside: int
            Resolution of Healpix maps
        fields: tuple(int) (optional, default=(0, 1, 2))
            Which fields to read in.
        idx: ndarray(int)
            Array of integers corresponding to the Healpix pixels to use.
        """
        self.npol = npol
        self.npix = hp.nside2npix(nside)
        self.nside = nside
        self.nfreqs = nfreqs
        self.data_shape = (self.npol, self.npix, self.nfreqs)
        self.data = np.empty(self.data_shape)
        self.variance = np.empty(self.data_shape)

        if idx is None:
            # use all pixels if slice is None
            self.indices = ...
        else:
            # otherwise restric to subset of pixels
            self.indices = idx

    def read_data_from_fits(self, data_iterator, fields=(0, 1, 2), verbose=False):
        for i, fname in enumerate(data_iterator):
            self.data[..., i] = np.array(hp.read_map(fname, verbose=verbose, field=fields))[:, self.indices]
  
    def read_variance_from_fits(self, var_iterator, fields=(0, 1, 2), verbose=False):
        for i, fname in enumerate(var_iterator):
            self.variance[..., i] = np.array(hp.read_map(fname, field=fields, verbose=verbose))[:, self.indices]

    def extract_with_mask(self, mask):
        """ Method to extract a region of the healpix map corresponding to a region
        defined with a boolean mask.

        Parameters
        ----------
        mask: ndarray(int)
            Boolean mask. Value is one in pixels to retain, 0 in pixels to discard.
        """
        self.partial_indices = np.where(mask==1)[0]
        self.partial_data = np.copy(self.data[:, self.partial_indices, :])
        self.partial_var = np.copy(self.variance[:, self.partial_indices, :])