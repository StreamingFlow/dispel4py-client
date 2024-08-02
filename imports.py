class SplitWords(IterativePE):

    def __init__(self):
        IterativePE.__init__(self)
        
    def _process(self, data):
        import os 
        #print("!!!SplitWords self.id %s, rankid %s, process.rank %s" % (self.id, os.getpid(), self.rank))	
        for word in data.split(" "):
            self.write("output", (word,1))
