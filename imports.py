class ReadSensorDataPE(ProducerPE):
    def __init__(self):
        ProducerPE.__init__(self)

    def _process(self, inputs):
        file = inputs['input']
        with open(file, 'r') as f:
            data = json.load(f)  # Load the entire JSON file
            for record in data:
                self.write('output', {'timestamp': record['timestamp'], 'temperature': float(record['temperature'])})
