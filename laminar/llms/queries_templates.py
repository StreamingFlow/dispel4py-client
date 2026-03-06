request_workflow_context_queries = [
    "You MUST propose a COMPLETE dispel4py WORKFLOW."
    "Whenever possible, use the available PEs to compose the workflow.",
    "Try to avoid using SimpleFunctionPE, as it cannot store state between iterations.",
    "The first PE must either be a GenericPE or a ProducerPE",
    "Use IterativePE whenever it gets one input and produces one output.",
    "Use ConsumerPE whenever it gets one input and produces no output.",
    "Use ProducerPE whenever it gets no input and produces one output.",
    "Use GenericPE whenever it can have many inputs and outputs.",
    "Always provide the __init__ method",

    "When using GenericPE, allways add input and output with self._add_input and self._add_output in the "
    "__init__ method.",

    "When using GenericPE, in the process method, to propagate results to the next step, use a call to "
    "self.write(<KEY>,<VALUE>), where <KEY> is the output name, and <VALUE> is the value of the data to be propagated"
    "For example self.write('output_to_consumer', statistics). Note that multiple self.write() calls can occur as long"
    "as they write different data to different value of <KEY>"

    "Never pass arguments to the __init__ method other than self.",

    "If a Processing Element (PE) requires input data from outside of the workflow execution context, it must receive "
    "it through the _process(self, data) method. The 'data' argument passed to process is a dictionary that always "
    "contains the key 'input'. Therefore, required external parameters must be accessed via data['input']. When "
    "executing the workflow with dispel4py, external inputs are provided using the -d argument as a JSON structure. "
    "For example: dispel4py simple int_ext_graph.py  -d '{\"read\": [{\"input\": \"coordinates.txt\"}]}'. "
    "Always assume that runtime inputs are delivered under the 'input' key inside the dictionary passed to process. ",

    "When defining Processing Elements (PEs) in a dispel4py workflow, the keys used to read and write data inside PEs "
    "must follow strict rules. First, every data key must be globally unique across the entire workflow. No two "
    "unrelated data streams may reuse the same key name. Second, if a producer PE writes data that a consumer PE reads, "
    "both PEs must use exactly the same key string. Third, data keys must follow the naming convention "
    "'ProducerName_to_ConsumerName'. For example, if PE A sends data to PE B, the key must be 'A_to_B'. PE A must write "
    "using 'A_to_B' and PE B must read using 'A_to_B'. Fourth, these data keys are internal to Processing Elements and "
    "must never be used as port names in graph.connect(). In every graph.connect() call, always use 'output' as the "
    "producer port name and 'input' as the consumer port name. Never use custom data keys such as 'A_to_B' in "
    "graph.connect(). This rule enforces deterministic data flow, prevents key collisions, and guarantees consistent "
    "workflow structure. In case PEs are reused, adapt the new PEs to the keys used in the reused PEs.",

    "When sending data to the next Processing Element (PE), you should use unless strictly required, python objects "
    "that are serializable to python. Try as much as possible to stick to Python primitive daya types like list tuples "
    "and dictionaries of primitive data types. Note that Numpy arrays are not serializable to JSON, so if you need to "
    "send a Numpy array, you should convert it to a list of lists or a list of dictionaries.",

    "For each proposed Processing Element, put the required external imports not only on a file level but also inside "
    "the _process() method",

    "Allways put on a file level import, the following imports: "
    "from dispel4py.base import GenericPE, IterativePE, ConsumerPE, ProducerPE",

    "Allways put on a file level import, the following import: from dispel4py.workflow_graph import WorkflowGraph",

    "Must include: YYYY = WorkflowGraph(), where YYYY is the variable that is instance of WorkflowGraph() and its "
    "name must reflect the workflow name",

    "Must include at least one: YYYY.connect(...), where YYYY is the variable that is instance of WorkflowGraph() and its "
    "name must reflect the workflow name",

    "Must include a sink/write PE (e.g., WriteJSONL) that is connected.",
    "Prefer composing from existing PEs listed below.",

    "If new PEs are created, ensure that all of them are being included in the \"new_pe\" list. This list should "
    "be in the returned json but not in the workflow source code",

    "If a processing element uses routines that requires complete objects, the object needs to be accumulated before "
    "being sent or before being used."

    "If a processing element uses libraries methods that requires array in input the array needs to be accumulated "
    "before calling the library method.",

    "Return JSON with the following format: { \"type\": \"workflow\", \"name\": \"...\", \"description\": \"...\", \"workflow_code\": "
    "\"...\", \"uses_pes\": [\"PE1\",\"PE2\",...], \"new_pe\": null OR [ { \"name\": \"...\", \"description\": \"...\", \"code\": \"...\" }, .. ] }",

    "avoid using yield whenever possible",

    "the argument data in the _process() method, is almost allways a dictionary, which keys are defined when connecting "
    "the workflow steps. It should hence not be used directly",

    "printf in the sink statements are not effective as they are not printed on the client side.",

    "Only for the sink workflow step, return the result to the laminar client in the following way:"
    "self.write('output', XXX), where the XXX template should be replaced with the variable that the workflow wants to "
    "propagate to the client side.",

    "Output valid Python code using WorkflowGraph."
]

request_description_queries = [
    "Explicitly states whether this is a Processing Element (PE) or a workflow.",
    "Clearly describes its role in a data-processing pipeline.",
    "Mentions expected inputs and outputs.",
    "Uses consistent technical vocabulary (e.g. filtering, transformation, signal processing, orchestration).",
    "Mentions important parameters or configuration options if obvious from the code."
    "The description should be suitable for: semantic similarity search and explaining results to users"
]
