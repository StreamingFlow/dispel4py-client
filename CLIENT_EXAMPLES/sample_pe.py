from dispel4py.core import GenericPE

class CountWords(GenericPE):
    def __init__(self):
        from collections import defaultdict
        GenericPE.__init__(self)
        self._add_input("input", grouping=[0])
        self._add_output("output")
        self.count = defaultdict(int)

    def _process(self, inputs):
        # print("!!!!CountWords self.id %s, rankid %s, process.rank %s" % (self.id, os.getpid(),self.rank))
        word, count = inputs['input']
        self.count[word] += count

    def _postprocess(self):
        self.write('output', self.count)