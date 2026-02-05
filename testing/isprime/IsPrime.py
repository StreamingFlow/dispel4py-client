from dispel4py.base import ProducerPE, IterativePE, ConsumerPE
from dispel4py.workflow_graph import WorkflowGraph
import random
from laminar.client.d4pyclient import d4pClient
import time
import pandas as pd
import numpy as np

class NumberProducer(ProducerPE):
    def __init__(self):
        ProducerPE.__init__(self)
        
    def _process(self, inputs):
        # this PE produces one input
        result= random.randint(1, 1000)
        return result

class IsPrime(IterativePE):
    def __init__(self):
        IterativePE.__init__(self)
    def _process(self, num):
        # this PE consumes one input and produces one output
        print("before checking data - %s - is prime or not\n" % num, end="")
        if all(num % i != 0 for i in range(2, num)):
            return num

class PrintPrime(ConsumerPE):
    def __init__(self):
        ConsumerPE.__init__(self)
    def _process(self, num):
        # this PE consumes one input
        print("the num %s is prime\n" % num, end="")


producer = NumberProducer()
isprime = IsPrime()
printprime = PrintPrime()

graph = WorkflowGraph()
graph.connect(producer, 'output', isprime, 'input')
graph.connect(isprime, 'output', printprime, 'input')

test_data = {
    10: {
        "simple": [],
        "multi": [],
        "redis": []
    },
    1000: {
        "simple": [],
        "multi": [],
        "redis": []
    },
    100000: {
        "simple": [],
        "multi": [],
        "redis": []
    }
}

client = d4pClient()
client.login("rosa", "1234") # Provide login details here

for inputValue in test_data.keys():
    for i in range(3):
        print(f"input {inputValue} ({i+1}/3)",end=" ",flush=True)
        start = time.time()
        client.run(graph,input=inputValue,verbose=False)
        test_data[inputValue]["simple"].append(time.time() - start)
        print("simple...", end=" ",flush=True)

        start = time.time()
        client.run_multiprocess(graph,input=inputValue,verbose=False)
        test_data[inputValue]["multi"].append(time.time() - start)
        print("multi...", end=" ",flush=True)

        start = time.time()
        client.run_dynamic(graph,input=inputValue,verbose=False)
        test_data[inputValue]["redis"].append(time.time() - start)
        print("redis...", end="\n",flush=True)

print(test_data)

index = test_data.keys()
simple = [np.average(x["simple"]) for x in test_data.values()]
multi = [np.average(x["multi"]) for x in test_data.values()]
redis = [np.average(x["redis"]) for x in test_data.values()]

df = pd.DataFrame({
    "simple": simple,
    "multi": multi,
    "redis": redis},
    index=index
)

ax = df.plot.barh(rot=0, title="Execution time of IsPrime workflow",figsize=(12.80,7.2),logx=True)

fig = ax.get_figure()
fig.supxlabel("Logarithmic average execution time (s)")
fig.supylabel("Workflow input")
fig.savefig("./is_prime_graph.png")
