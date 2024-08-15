#Sample workflow for which we use to interact with Laminar framework using several Laminar Client functions

from dispel4py.base import ProducerPE, IterativePE, ConsumerPE
from dispel4py.workflow_graph import WorkflowGraph
import random
from client import d4pClient,Process

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


client = d4pClient()

#Create User and Login 
#print("\n Create User and Login \n")
#client.register("root","root")

client.login("root","root")

print("\n Register Graph \n")
client.register_Workflow(graph,"graph_sample")


print("\n Literal to Search on PEs \n")
results=client.search_Registry_Literal("prime","pe")
for r in results:
    print(r)


print("\n Text to Code Search on PEs\n")
results=client.search_Registry_Semantic("checks prime numbers","pe")
for r in results:
    print(r)

print("\n Code to Text Search (Code Recommendation) on PEs \n")
results=client.code_Recommendation("random.randint(1, 1000)","pe")
for r in results:
    print(r)


# Run the workflow serverless

##SIMPLE (Sequential)
print("\n Running the Workflow Sequentially\n")
r=client.run(graph,input=100)
print(r)

##MULTI
print("\n Running the Workflow in Parallel - Multi mapping\n")
client.run_multiprocess(graph,input=100)

##DYNAMIC (Redis)
print("\n Running the Workflow Dynamically - Redis mapping\n")
client.run_dynamic(graph,input=100)
