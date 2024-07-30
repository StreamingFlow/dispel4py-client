class PrintPrime(ConsumerPE):
    def __init__(self):
        ConsumerPE.__init__(self)
        self.prime=[]
    def _process(self, num):
        # this PE consumes one input
        print("the num %s is prime\n" % num, end="")
        self.prime.append(num)
