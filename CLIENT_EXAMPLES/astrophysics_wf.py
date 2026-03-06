from dispel4py.base import IterativePE, GenericPE
from dispel4py.workflow_graph import WorkflowGraph
from laminar.client.d4pyclient import d4pClient


class ReadRaDec(GenericPE):

    def __init__(self):
        GenericPE.__init__(self)
        self._add_output('output')

    def _process(self, inputs):
        file = inputs['input']
        print('Reading file %s' % file)
        with open(file) as f:
            count = 0
            for line in f:
                count += 1
                ra, dec = line.strip().split(',')
                self.write('output', [count, ra, dec, 0.001])


class GetVOTable(IterativePE):

    def __init__(self):
        IterativePE.__init__(self)

    def _process(self, data):
        import requests
        count, ra, dec, sr = data
        print('reading VOTable RA=%s, DEC=%s' % (ra, dec))
        url = 'http://vizier.u-strasbg.fr/viz-bin/votable/-A?-source=VII/237&RA=%s&DEC=%s&SR=%s' % (ra, dec, sr)
        response = requests.get(url)
        return [count, ra, dec, response.text]


class FilterColumns(IterativePE):

    def __init__(self, columns=None):
        IterativePE.__init__(self)
        if columns is None:
            columns = ['MType', 'logR25']
        self.columns = columns

    def _process(self, data):
        import io
        from astropy.io.votable import parse_single_table
        count, ra, dec, votable_xml = data
        table = parse_single_table(io.BytesIO(votable_xml.encode('utf-8')), pedantic=False)
        results = [count, ra, dec]

        for c in self.columns:
            try:
                value = table.array[c].data[0]  # we assume that there's only one row in the table
            except:
                value = None
            results.append(value)
            print('extracted column: %s = %s' % (c, value))
        return results


class InternalExtinction(IterativePE):

    def internal_extinction(self, mtype, logr25, C=0.04):
        import math
        if mtype in self.type_dict:
            type = float(self.type_dict[mtype])
        else:
            type = -10.

        k = 0.754 * 10 ** (-0.2 * type)
        if k > 1.:
            k = 1.

        # Calculating K2

        if type < 0:
            K2 = 0.12 - 0.007 * type
        else:
            K2 = 0.094
        # Calculating R
        R = 10. ** logr25

        # Finally it calculates ai
        # ai=-2.5*log(k+(1.0-k)*R*((2.0*C*(1+0.2/K2)-1)))
        tmp = 2 * C * (1 + 0.2 / K2) - 1

        ai = -2.5 * math.log10(k + (1 - k) * R ** tmp)

        return type, ai

    def __init__(self):
        IterativePE.__init__(self)
        self.type_dict = {"E": -5, "E-S0": -3, "S0": -2, "S0a": 0, "Sa": 1, "Sab": 2, "Sb": 3, "Sbc": 4, "Sc": 6,
                          "Scd": 7,
                          "Sd": 8, "Sm": 9, "SBa": 1, "SBab": 2, "SBb": 3, "SBbc": 4, "SBc": 6, "SBcd": 7, "SBd": 8,
                          "SBm": 9}

    def _process(self, data):
        count, ra, dec = data[0:3]
        mtype = data[3]
        logr25 = data[4]
        print("!! DATA mytype:%s, logr25:%s" % (mtype, logr25))
        try:
            t, ai = self.internal_extinction(mtype, logr25)
            result = [count, ra, dec, mtype, logr25, t, ai]
            print('internal extinction: %s' % result)
            return result
        except:
            print('KIG%s: failed to calculate internal extinction' % count)


astro_graph = WorkflowGraph()
read = ReadRaDec()
votab = GetVOTable()
filt = FilterColumns()
intext = InternalExtinction()

astro_graph.connect(read, 'output', votab, 'input')
astro_graph.connect(votab, 'output', filt, 'input')
astro_graph.connect(filt, 'output', intext, 'input')