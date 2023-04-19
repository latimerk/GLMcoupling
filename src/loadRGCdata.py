import h5py
import numpy as np

def loadStim(use_repeat=False, data_dir='Data'):
    F = h5py.File(data_dir + '/JN05_RGC_expt3_upsampled.hdf5','r')
    if use_repeat:
        return np.array(F["Rep_Stim"])
    else:
        return np.array(F["Stim"])

def loadSpikes(use_repeat=False, data_dir='Data'):
    F = h5py.File(data_dir + '/JN05_RGC_expt3_upsampled.hdf5','r')
    numCells = 9;

    spks = list()
    for ii in range(numCells):
        fName = "Spks_" + str(ii) 
        if use_repeat:
            fName = "Rep_" + fName
        spks.append(np.array(F[fName]))

    return spks;

