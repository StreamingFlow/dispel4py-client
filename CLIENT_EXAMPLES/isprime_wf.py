from dispel4py.base import ProducerPE, IterativePE, ConsumerPE
from dispel4py.workflow_graph import WorkflowGraph
import random

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
        #print("before checking data - %s - is prime or not\n" % num, end="")
        if all(num % i != 0 for i in range(2, num)):
            return num

class PrintPrime(ConsumerPE):
    def __init__(self):
        ConsumerPE.__init__(self)
        self.prime=[]
    def _process(self, num):
        # this PE consumes one input
        print("the num %s is prime\n" % num, end="")
        self.prime.append(num)
    def _postprocess(self):
        self.write('output', self.prime)

producer = NumberProducer()
isprime = IsPrime()
printprime = PrintPrime()

isprime_wf = WorkflowGraph()
isprime_wf.connect(producer, 'output', isprime, 'input')
isprime_wf.connect(isprime, 'output', printprime, 'input')

