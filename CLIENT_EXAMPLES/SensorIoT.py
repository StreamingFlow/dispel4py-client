#Example of a IsPrime workflow running it with client functions

from dispel4py.base import IterativePE, ConsumerPE, ProducerPE
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
            print("data is %s" % data)
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

class AggregateDataPE(ConsumerPE):
    def __init__(self):
        ConsumerPE.__init__(self)
        self.temperatures = []

    def _process(self, data):
        self.temperatures.append(data['temperature'])
        if len(self.temperatures) % 5 == 0:  # Every 5 readings
            avg_temp = np.mean(self.temperatures)
            print(f"Average temperature of last 5 readings: {avg_temp}")
            self.temperatures = []  # Reset for the next batch

# Create PEs
read = ReadSensorDataPE()
read.name = 'read'
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

client = d4pClient()

#Create User 
#print("\n Create User and Login \n")
#client.register("root","root")

#Login
client.login("root","root")

input=[{'input' : "sensor_data_1000.json"}]
resources=["sensor_data_1000.json"]


# Run the workflow serverless

##SIMPLE 
a=client.run(graph,input=input, resources=resources, verbose=True)
print(a)

##MULTI
#b=client.run_multiprocess(graph,input=input, resources=resources,  verbose=True)
#print(b)

##REDIS 
#client.run_dynamic(graph,input=input, resources=resources,  verbose=True)
#print(c)
