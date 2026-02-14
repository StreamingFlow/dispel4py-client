from dispel4py.base import IterativePE, ConsumerPE, ProducerPE, GenericPE
from dispel4py.workflow_graph import WorkflowGraph
import numpy as np
import json

class ReadSensorDataPE(ProducerPE):
    def __init__(self):
        ProducerPE.__init__(self)

    def _process(self, inputs):
        file = inputs['input']
        with open(file, 'r') as f:
            data = json.load(f)  # Load the entire JSON file
            for record in data:
                self.write('output', {'timestamp': record['timestamp'], 'temperature': float(record['temperature'])})

class NormalizeDataPE(IterativePE):
    def __init__(self):
        IterativePE.__init__(self)

    def _process(self, data):
        temp = data['temperature']
        # Example normalization: scale temperature to 0-1 based on expected range 0-40 degrees Celsius
        normalized_temp = (temp - 0) / (40 - 0)
        data['normalized_temperature'] = normalized_temp
        return data

class AnomalyDetectionPE(IterativePE):
    def __init__(self, threshold=0.1):
        IterativePE.__init__(self)
        self.threshold = threshold
        self.temperatures = []

    def _process(self, data):
        temp = data['normalized_temperature']
        self.temperatures.append(temp)
        mean_temp = np.mean(self.temperatures)
        if abs(temp - mean_temp) > self.threshold:
            data['anomaly'] = True
        else:
            data['anomaly'] = False
        return data

class AlertingPE(IterativePE):
    def __init__(self):
        IterativePE.__init__(self)
        
    def _process(self, data):
        if data.get('anomaly', False):
            alert_message = f"Anomaly detected at {data['timestamp']}: Temperature={data['temperature']}, Normalized Temp is {data['normalized_temperature']}"
            print(alert_message)
        return data

class AggregateDataPE(GenericPE):
    def __init__(self):
        GenericPE.__init__(self)
        self._add_input("input")
        self._add_output("output")
        self.temperatures = []
        self.avg_temp = float(0)

    def _process(self, inputs):
        t=inputs['input']
        self.temperatures.append(t['temperature'])
        if len(self.temperatures) % 5 == 0:  # Every 5 readings
            self.avg_temp = np.mean(self.temperatures)
            print(f"Average temperature of last 5 readings: {self.avg_temp}")
            self.temperatures = []  # Reset for the next batch
            self.write('output', self.avg_temp)


# Create PEs
read = ReadSensorDataPE()
normalize_data = NormalizeDataPE()
alerting = AlertingPE()
anomaly_detection = AnomalyDetectionPE()
aggregate_data = AggregateDataPE()

# Create the workflow graph
sensorWorkflow = WorkflowGraph()
sensorWorkflow.connect(read, 'output', normalize_data, 'input')
sensorWorkflow.connect(normalize_data, 'output', anomaly_detection, 'input')
sensorWorkflow.connect(anomaly_detection, 'output', alerting, 'input')
sensorWorkflow.connect(alerting, 'output', aggregate_data, 'input')


