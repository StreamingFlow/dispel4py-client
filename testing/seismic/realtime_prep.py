from dispel4py.core import GenericPE
from dispel4py.base import BasePE, IterativePE, ConsumerPE, create_iterative_chain
from dispel4py.workflow_graph import WorkflowGraph
from obspy.signal.util import next_pow_2
from dispel4py.new.simple_process import process as simple_process
from scipy.fftpack import fft
import numpy as np
from numpy import linspace
import os
import traceback
from client import d4pClient
# import matplotlib as mpl
# mpl.use('Agg')
# import matplotlib.pyplot as plt
import glob
import re
#import obspy
import subprocess
import time
import pandas as pd

from numpy import sign, arange, zeros, absolute, true_divide, sum,  floor, convolve, amax, logical_and
from numpy import arange, sqrt, abs, multiply, conjugate, real
import copy

def spectralwhitening_smooth(stream, N):
    """
    Apply spectral whitening to data.
    Data is divided by its smoothed (Default: None) amplitude spectrum.
    """
    stream2 = copy.deepcopy(stream)
    
    for trace in arange(len(stream2)):
        data = stream2[trace].data
        
        n = len(data)
        nfft = nextpow2(n)
        
        spec = fft(data, nfft)
        spec_ampl = sqrt(abs(multiply(spec, conjugate(spec))))
        
        spec_ampl = smooth(spec_ampl, N)        
        
        spec /= spec_ampl  #Do we need to do some smoothing here?
        ret = real(ifft(spec, nfft)[:n])
        
        stream2[trace].data = ret
        
    return stream2


def onebit_norm(stream):
    stream2 = copy.deepcopy(stream)
    
    for trace in arange(len(stream2)):
        data = stream2[trace].data
        data = sign(data)
        stream2[trace].data = data
        
    return stream2


def mean_norm(stream,N):
    stream2 = copy.deepcopy(stream)
    
    for trace in arange(len(stream2)):
        data = stream2[trace].data
        
        w = zeros(len(data)) 
        naux = zeros(len(data))
        
        for n in arange(len(data)):
            if n<N:
                tw = absolute(data[0:n+N])
            elif logical_and(n>=N, n<(len(data)-N)):
                tw = absolute(data[n-N:n+N])
            elif n>=(len(data)-N):
                tw = absolute(data[n-N:len(data)])
                
            w[n]=true_divide(1,2*N+1)*(sum(tw))
            
        naux=true_divide(data,w)
        stream2[trace].data = naux
        
    return stream2


def gain_norm(stream, N):
    from scipy.signal import triang
    stream2 = copy.deepcopy(stream)
    
    for trace in arange(len(stream2)):
        data = stream2[trace].data
        
        dt = 1./(stream2[trace].stats.sampling_rate)
        L = floor((N/dt+1./2.))
        h = triang(2.*L+1.)
        
        e = data**2.
       
        rms = (convolve(e,h,'same')**0.5)
        epsilon = 1.e-12*amax(rms)
        op = rms/(rms**2+epsilon)
        dout = data*op
        
        stream2[trace].data = dout
        
    return stream2

def env_norm(stream, N):
    from obspy.signal import util
    stream2 = copy.deepcopy(stream)
    
    for trace in arange(len(stream2)):
        data = stream2[trace].data
        norm = util.smooth(absolute(data), N)
        #normdata = cpxtrace.normEnvelope(data, fs=stream2[trace].stats.sampling_rate, smoothie=N, fk=[1, 1, 1, 1, 1] )
        
        normdata = true_divide(data,norm)
        stream2[trace].data = normdata
        
    return stream2


        
#from obspy import UTCDateTime
#from obspy.core.stream import Stream
class StreamRead(IterativePE):
    
    def __init__(self):
        IterativePE.__init__(self)
        
    def _process(self, filename):
        from obspy.core import read

        # open the filename, and get each station and find its corresponding stream data file
        with open(filename, 'r') as f:
            print(filename)
            for station in f.readlines():
                
                network, station_name = station.split()
                
                stream_file = glob.glob('./stream_%s_%s_*.mseed' % (network, station_name))
                
                if stream_file:
                    counter = re.findall(r'stream_(.+)_(.+)_(.+).mseed', stream_file[0])[0][2]
                    self.write('output', [stream_file[0], station_name, counter, network])

                else:
                	self.log('Failed to find %s %s' % (network, station_name))

class StreamToFile(ConsumerPE):
    
    def __init__(self):
        ConsumerPE.__init__(self)
        
    def _process(self, data):
        str1 = data[0]
        station= data[1]
        counter = data[2]

        dir = './DATA/'+ starttime
        if not os.path.exists(dir):
            os.makedirs(dir)
        directory = dir +'/'+ station
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        try:
            fout = directory+'/%s_%s_preprpcessed.SAC' % (station, counter)
        except TypeError:
            # maybe there's no "%s" in the string so we ignore count - bad idea?
            fout = file_dest
        
        np.save(fout, str1)



def factors(n):
    return [(i, n / i) for i in range(1, int(n**0.5)+1) if n % i == 0]


def factors(n):
    return [(i, n / i) for i in range(1, int(n**0.5)+1) if n % i == 0]


class Decimate(IterativePE):
    
    def __init__(self, sps):
        IterativePE.__init__(self)
        self.sps = sps
    
    def _process(self, data):
        from obspy.core import read
        str1 = read(data[0])
        
        str1.decimate(int(str1[0].stats.sampling_rate/self.sps))
        
        j = int(str1[0].stats.sampling_rate/self.sps)
        
        if j > 16:
            facts=factors(j)[-1]
            str1[0].decimate(facts[0])
            str1[0].decimate(facts[1])
        else:
            str1[0].decimate(j)
        
        data[0] = str1
        return data


class Detrend(IterativePE):
    
    def __init__(self):
        IterativePE.__init__(self)
    
    def _process(self, data):
        
        data[0].detrend('simple')
        return data

class Demean(IterativePE):
    
    def __init__(self):
        IterativePE.__init__(self)
        
    def _process(self, data):
        
        data[0].detrend('demean')
        return data


class RemoveResponse(IterativePE):
    
    def __init__(self, pre_filt, units):
        IterativePE.__init__(self)
        self.pre_filt = pre_filt
        self.units = units
    
    def _process(self, data):
        from obspy import read_inventory
        # read the corresponding inventory file in order to get response later
        inv = read_inventory('./%s_inventory.xml' % data[-1])
        data[0].remove_response(inv, output=self.units, pre_filt=self.pre_filt)
        
        return data


class Filter(IterativePE):
    
    def __init__(self, freqmin=0.01, freqmax=1., corners=4, zerophase=False):
        IterativePE.__init__(self)
        self.freqmin = freqmin
        self.freqmax = freqmax
        self.corners = corners
        self.zerophase= zerophase
    
    def _process(self, data):
        
        data[0].filter('bandpass', freqmin=self.freqmin, freqmax=self.freqmax, \
                corners=self.corners, zerophase=self.zerophase)
        return data


class CalculateNorm(IterativePE):
    
    def __init__(self, norm, N):
        IterativePE.__init__(self)
        self.norm = norm
        self.N = N
    
    def _process(self, data):
        
        if self.norm is 'onebit':
            data[0] = onebit_norm(data[0])
        
        elif norm is 'mean':
            data[0] = mean_norm(data[0], self.N)
        
        elif norm is 'gain':
            data[0] = gain_norm(data[0], self.N)
        
        elif norm is 'env':
            data[0] = env_norm(data[0], self.N)
        
        return data


class Whiten(IterativePE):
    
    def __init__(self, smooth):
        IterativePE.__init__(self)
        self.smooth = smooth
    
    def _process(self, data):
        
        if self.smooth is not None:
            data[0] = spectralwhitening_smooth(data[0], smooth)
        
        return data


class CalculateFft(IterativePE):
    
    def __init__(self, type, shift):
        IterativePE.__init__(self)
        self.type = type
        self.shift = shift
    
    def _process(self, data):
        if self.type is not None:
            str_data = data[0][0].data
            N1 = len(str_data)
            str_data = str_data.astype(self.type)
            
            size = max(2 * self.shift + 1, (N1) + shift)
            nfft = next_pow_2(size)
            
            print ("station %s and network %s - size in calc_fft %s " % \
                (data[0][0].stats['station'], data[0][0].stats['network'], size)) 
            
            IN1 = fft(str_data, nfft)
            return [IN1, data[1], data[2]]
        else:
            return [data[0][0].data, data[1], data[2]] 


ROOT_DIR = './OUTPUT/'
starttime='2020-06-01T06:00:00.000'
endtime='2020-06-01T07:00:00.000'


streamRead=StreamRead()
streamRead.name = 'streamRead'
streamToFile = StreamToFile()
streamToFile.name='StreamToFile'

decim = Decimate(4)
detrend = Detrend()
demean = Demean()

pre_filt = (0.005, 0.006, 30.0, 35.0)
units = 'VEL'
removeResponse = RemoveResponse(pre_filt, units)

filt = Filter()

norm = 'env'
N = 15
calNorm = CalculateNorm(norm, N)

whiten = Whiten(None)

type = 'float64'
shift = 5000
calcFft = CalculateFft(type, shift)

graph = WorkflowGraph()

graph.connect(streamRead, StreamRead.OUTPUT_NAME, decim, 'input')
graph.connect(decim, 'output', detrend, 'input')
graph.connect(detrend, 'output', demean, 'input')
graph.connect(demean, 'output', removeResponse, 'input')
graph.connect(removeResponse, 'output', filt, 'input')
graph.connect(filt, 'output', calNorm, 'input')
graph.connect(calNorm, 'output', whiten, 'input')
graph.connect(whiten, 'output', calcFft, 'input')
graph.connect(calcFft, 'output', streamToFile, StreamToFile.INPUT_NAME)

client = d4pClient()
client.login("sam","123")


test_data = {
    "simple": [],
    "multi": [],
    "redis": []
}

client.run_multiprocess(graph, input=[{"input": 'Copy-Uniq-OpStationList-NetworkStation.txt'}], resources=["AK_inventory.xml", "Copy-Uniq-OpStationList-NetworkStation.txt", "stream_AK_BMR_0.mseed"], verbose=False)

for i in range(3):
    print(f"({i+1}/3)",end=" ",flush=True)
    start = time.time()
    client.run(graph, input=[{"input": 'Copy-Uniq-OpStationList-NetworkStation.txt'}], resources=["AK_inventory.xml", "Copy-Uniq-OpStationList-NetworkStation.txt", "stream_AK_BMR_0.mseed"], verbose=False)
    test_data["simple"].append(time.time() - start)
    print("simple...", end=" ",flush=True)

    start = time.time()
    client.run_multiprocess(graph, input=[{"input": 'Copy-Uniq-OpStationList-NetworkStation.txt'}], resources=["AK_inventory.xml", "Copy-Uniq-OpStationList-NetworkStation.txt", "stream_AK_BMR_0.mseed"], verbose=False)
    test_data["multi"].append(time.time() - start)
    print("multi...", end=" ",flush=True)

    start = time.time()
    client.run_dynamic(graph, input=[{"input": 'Copy-Uniq-OpStationList-NetworkStation.txt'}], resources=["AK_inventory.xml", "Copy-Uniq-OpStationList-NetworkStation.txt", "stream_AK_BMR_0.mseed"], verbose=False)
    test_data["redis"].append(time.time() - start)
    print("redis...", end="\n",flush=True)

print(test_data)

df = pd.DataFrame({"mappings": ["simple","multiprocessing","redis"], "Average speed": [np.average(test_data["simple"]), np.average(test_data["multi"]), np.average(test_data["redis"])]})

ax = df.plot.barh(rot=0, title="Execution time of seismic preperation workflow",figsize=(12.80,7.2))

fig = ax.get_figure()
fig.supxlabel("Mapping type")
fig.supylabel("Execution time (s)")
fig.savefig("./seismic_preperation.png")
