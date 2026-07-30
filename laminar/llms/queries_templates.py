PE_AUTHORING_RULES = [

    "Try to avoid using SimpleFunctionPE, as it cannot store state between iterations.",

    "Use IterativePE whenever it gets one input and produces one output.",

    "Use ConsumerPE whenever it gets one input and produces no output.",

    "Use ProducerPE whenever it gets no input and produces one output.",

    "Use GenericPE whenever it can have many inputs and/or many outputs.",

    "Always provide the __init__ method.",

    "Never pass arguments to the __init__ method other than self.",

    "When using GenericPE, declare every port in __init__ with self._add_input(<PORT>) "
    "and self._add_output(<PORT>). IterativePE, ConsumerPE and ProducerPE already "
    "provide their ports ('input' and/or 'output'), so do not re-declare them.",

    "PORT / KEY / CONNECT IDENTITY RULE. A port name, the key used in self.write() "
    "and in reads, and the port argument in graph.connect() are the SAME identifier "
    "and must match exactly for a given edge. There is no separate 'data key' that "
    "differs from the port name. Rules: "
    "(a) For an edge from producer A to consumer B, the name passed to A's "
    "self._add_output(...) is the name A writes to with self.write(...) and the name "
    "used for A in graph.connect(...); likewise the name passed to B's "
    "self._add_input(...) is the name B reads and the name used for B in "
    "graph.connect(...). "
    "(b) For single-stream PEs (IterativePE, ConsumerPE, ProducerPE, and simple "
    "single-input/single-output GenericPEs) use the default names 'output' for the "
    "output port and 'input' for the input port. "
    "(c) For GenericPEs that carry several distinct streams, give each port a unique "
    "descriptive name following the convention 'Producer_to_Consumer' (e.g. 'A_to_B') "
    "and use that exact name in self._add_output/self._add_input, in self.write()/reads, "
    "AND in graph.connect(). "
    "(d) Every port name must be unique within a PE; an inter-PE name is shared by "
    "exactly the two PEs it connects.",

    "When using GenericPE, propagate a result to the next step with "
    "self.write(<PORT>, <VALUE>), where <PORT> is the exact name of an output port "
    "declared with self._add_output(<PORT>) in __init__, and <VALUE> is the data to "
    "propagate. For example self.write('Stats_to_Writer', statistics). Multiple "
    "self.write() calls are allowed as long as each targets a different declared "
    "output port.",

    "HOW TO READ THE INPUT inside the process method depends on the PE type. "
    "In a GenericPE the process argument is a dict keyed by the PE's input port names; "
    "read each value by its port name (e.g. data['input'] or data['A_to_B']). Never "
    "assume a hard-coded key for a GenericPE: index by the input port name you declared "
    "in __init__. In an IterativePE or ConsumerPE the process argument is the single, "
    "already-unwrapped input value; use it directly and do NOT index it.",

    "EXTERNAL RUNTIME INPUTS (data from outside the workflow) are delivered to the "
    "FIRST PE under the key 'input', and are supplied to dispel4py via the -d argument "
    "as a JSON structure keyed by the first PE's instance name. For example: "
    "dispel4py simple int_ext_graph.py -d '{\"read\": [{\"input\": \"coordinates.txt\"}]}'. "
    "If the first PE is a GenericPE, read this value as data['input']; if it is an "
    "IterativePE/ConsumerPE, the value is delivered directly as the process argument.",

    "When sending data to the next PE, prefer objects that serialize cleanly, ideally "
    "JSON-serializable. Stick to Python primitives and lists/tuples/dicts of primitives "
    "as much as possible. Numpy arrays are NOT JSON-serializable, so convert them to "
    "lists (e.g. a list of lists or a list of dicts) before writing them.",

    "If a routine requires a complete object before it can run, or a library method "
    "requires a full array as input, accumulate the data across iterations first, then "
    "send it / call the routine once it is complete.",

    "For each proposed PE, place the required external imports both at file level and "
    "inside the process method, with a comment above each in-method import explaining "
    "what it is needed for.",

    "Always include at file level: "
    "from dispel4py.base import GenericPE, IterativePE, ConsumerPE, ProducerPE",

    "Avoid using yield whenever possible.",

    "NEW-PE STUBBING RULE (applies ONLY to newly created PEs that contain genuine "
    "business logic; it does NOT apply to reused PEs or to pure-boilerplate PEs such "
    "as the sink/write PE, which must be fully implemented). To avoid hallucinated "
    "logic, do not write the business logic yourself. Instead set up all dispel4py "
    "boilerplate: in __init__ declare every input and output port; in the process "
    "method include the full I/O wiring (self.write(...) for GenericPE, or return for "
    "IterativePE/ProducerPE). In the process method, describe the exact input format "
    "and the expected output format extensively in comments, optionally with a "
    "pseudo-algorithm in comments. Then insert raise NotImplementedError(...) as the "
    "FIRST executable statement, immediately after those comments and BEFORE the "
    "write/return, so that running the PE fails until the user implements it. Keep the "
    "now-unreachable write/return statements in the body on purpose: this unreachable "
    "code documents the required wiring and must not be deleted. The exception replaces "
    "ONLY the business logic, never the input/output wiring.",
]

WORKFLOW_GRAPH_RULES = [

    "You MUST propose a fully WIRED dispel4py workflow SKELETON. 'Wired' means every PE, "
    "port, graph.connect() and the sink are present and consistent. The workflow is "
    "deliberately NOT runnable: each newly created PE MUST raise NotImplementedError as the "
    "first statement of its process method. Writing working business-logic bodies is a "
    "FAILURE, not success.  The ONLY thing allowed to remain "
    "unimplemented is the business logic of a newly created PE (see the new-PE "
    "rule below); everything else, including all wiring and the sink, must work.",

    "Whenever possible, use the available PEs to compose the workflow. suh PEs must be included in the proposed "
    "workflow, copying them line by line, and not importing them from an 'available_pes' "
    "module, as there is no such thing.",

    "The first PE must either be a GenericPE or a ProducerPE.",

    "graph.connect() always uses the producer's output port name and the consumer's "
    "input port name, exactly as declared on those PEs. For single-stream PEs this is "
    "graph.connect(A, 'output', B, 'input'). For multi-stream GenericPEs use the "
    "matching unique names, e.g. graph.connect(A, 'A_to_B', B, 'A_to_B').",

    "WorkflowGraph.connect is the only way to add PEs to a Dispel4py workflow. Calling connect will "
    "automatically register an instance of a processing element in the processed workflow. different "
    "connections (edges) starting from the same instance of a PE generates a broadcast pattern. "
    "Different connect to the same instance of Processing Elements implements a gather pattern.",

    "Always include at file level: from dispel4py.workflow_graph import WorkflowGraph",

    "Must include: YYYY = WorkflowGraph(), where YYYY is the variable holding the "
    "WorkflowGraph instance and its name reflects the workflow name.",

    "Must include at least one: YYYY.connect(...), on that same WorkflowGraph instance "
    "YYYY.",

    "Must include, unless user explicitly stated that it is not required, a sink/write PE "
    "(e.g. WriteJSONL) that is connected. The sink is "
    "pure boilerplate, so it must be FULLY implemented and runnable; it is never left "
    "as a NotImplementedError stub.",

    "Prefer composing from existing PEs listed below.",

    "Do not rely on print() inside the sink: printed output is not delivered to the "
    "Laminar client.",

    "Only the sink/write PE returns its result to the Laminar client, by calling "
    "self.write('output', XXX), where XXX is the variable to propagate to the client "
    "side. The sink's output port must therefore be named 'output' and declared in its "
    "__init__.",
]

WORKFLOW_OUTPUT_RULES = [

    "If new PEs are created, include all of them in the 'new_pe' list of the returned "
    "JSON. This list must NOT appear in the workflow source code.",

    "Output valid Python code using WorkflowGraph.",

    "Return JSON with the following format: { \"type\": \"workflow\", \"name\": \"...\", "
    "\"description\": \"...\", \"workflow_code\": \"...\", \"uses_pes\": [\"PE1\",\"PE2\",...], "
    "\"new_pe\": null OR [ { \"name\": \"...\", \"description\": \"...\", \"code\": \"...\" }, ... ] }",
]

REQUEST_NEW_WORKFLOW_CONTEXT_QUERIES = (
        WORKFLOW_GRAPH_RULES
        + PE_AUTHORING_RULES
        + WORKFLOW_OUTPUT_RULES
)

EVALUATE_QUALITY_REQUESTED_WORKFLOW_CONTEXT_QUERIES = [
    "You are a strict reviewer of dispel4py workflows. You are given the user query "
    "and a proposed workflow, and you must decide whether the workflow correctly and "
    "completely answers that query.",

    "IMPORTANT: the proposed code is a TEMPLATE / skeleton. Newly created PEs "
    "deliberately do not implement business logic and contain a "
    "raise NotImplementedError(...) placeholder, with the real write()/return left in "
    "place but unreachable. This is intentional and is NOT an issue. Never report the "
    "missing business logic, the NotImplementedError, or the unreachable write/return "
    "as problems.",

    "Only report problems that would make the workflow fail to satisfy the user query "
    "or break its structure: a step that does not match what the user asked for, the "
    "wrong PE type, missing or mismatched ports, broken data flow, a missing or "
    "unconnected sink, or a result that would never be returned to the client.",

    "Do NOT report as error types mismatch in not implemented process() methods, "
    "as thy should be implemented by the user. Just report if the output or input "
    "port names do not match across Processing elements",

    "EXTREMELY IMPORTANT: DO NOT REPORT error related to the fact that code is a template. "
    "If a function is merely a template this is wanted behaviour.",

    "This warning: 'The workflow is only a skeleton', is not an error but a wanted feature",

    "If new Processing Elements contains implemented code, this is an issue, as they should raise "
    "a NotImplementedError(...), since the business logic must be provided by the user.",

    "Return JSON ONLY, with double-quoted keys and strings, in exactly this shape: "
    '{ "issues": ["issue 1", "issue 2", "..."] }. '
    "Each issue must be a short, specific, actionable string. If the workflow is "
    "correct or good enough to answer the query, return an empty list: "
    '{ "issues": [] }. '
    "Output nothing except this JSON object (no prose, no markdown, no code fences).",
]

REQUEST_DESCRIPTION_CONTEXT_QUERIES = [
    "You are to describe either a Dispel4py workflow or a Dispel4py Processing Element (PE).",
    "The description must be suitable for semantic similarity search and for explaining results to users.",
    "The 'inputs' field is an array of strings. Each string names an expected input and its type, "
    "for example \"signal: numpy.ndarray\". Use an empty array [] if the component takes no inputs.",
    "The 'outputs' field is an array of strings. Each string names a produced output and its type, "
    "for example \"filtered_signal: numpy.ndarray\". Use an empty array [] if the component produces no outputs.",
    "The 'tags' field is an array of short keyword strings for retrieval, drawn from consistent technical "
    "vocabulary (e.g. filtering, transformation, signal processing, orchestration).",
    "The 'description' field is a single JSON string containing plain text. It is organised into four "
    "sections, each introduced by a plain-text heading written in uppercase on its own line: "
    "COMPONENT TYPE, SUMMARY, ROLE, PARAMETERS. Separate the sections with newline escapes (\\n). "
    "Use no markdown, no JSON sub-keys and no bullet points: under each heading the content is written "
    "as flowing prose sentences.",
    "Under COMPONENT TYPE, state explicitly whether the component is a Processing Element (PE) or a workflow.",
    "Under SUMMARY, give a one- or two-sentence overview of the component.",
    "Under ROLE, explain the component's function within a data-processing pipeline, describing in words "
    "the data it consumes and produces so the section is self-contained.",
    "Under PARAMETERS, state the configuration options evident from the code, or state explicitly that "
    "the component takes no parameters.",
    "Use consistent technical vocabulary throughout (filtering, transformation, signal processing, "
    "orchestration).",
    "Return ONLY a valid JSON object, with no markdown fences and no text before or after it.",
    """
    Return exactly this JSON structure:
    {{
        "inputs": ["<name: type>", "..."],
        "outputs": ["<name: type>", "..."],
        "tags": ["<keyword>", "..."],
        "description": "COMPONENT TYPE\\n<prose>\\n\\nSUMMARY\\n<prose>\\n\\nROLE\\n<prose>\\n\\nPARAMETERS\\n<prose>"
    }}
    """,
]

REGISTER_BASE_QUERIES = [
    "Return JSON only. Do not explain.",
    """Return JSON only, describing the code, the inputs and the outputs:
        {{
            'description': '...',
            'inputs':  '<input_name>:<description>\n...',
            'outputs': '<output_name>:<description>\n...',
            'tags' : ['tag1', 'tag2', ...]
        }}""",
    "<description> is a placeholder for the description of the input or output;",
    "If either no input or output is available, return null;",
    "Ensure that the description contains all the information and is not verbose or repetitive;",
    "in the 'description' JSON object that you will return, you need to put the description of the code that has been provided to you;",
    "If for some reason you are not able to satisfy this request, put in the description the reason why you cannot reply;",
]

REGISTER_PE_CONTEXT_QUERIES = REGISTER_BASE_QUERIES + [
    "The <input_name> and <output_name> arguments are placeholders for the processing element channels used to communicate;",
    "Tags is a list of keywords that describe the Processing element, so that it may be categorized;",
]

REGISTER_WORKFLOW_CONTEXT_QUERIES = REGISTER_BASE_QUERIES + [
    "The <input_name> and <output_name> arguments are placeholders for the workflow user inputs and workflow output;",
    "Tags is a list of keywords that describe the workflow, so that it may be categorized;",
]

NAME_WORKFLOW_QUERY = """You are naming a Dispel4py workflow based on its source code.

The code below contains the workflow's processing elements (PEs) and their logic.
Propose ONE concise, descriptive name that reflects what the workflow does.

Rules:
- Respond with JSON ONLY — no quotes, no explanation, no surrounding text. 
- format of output data should be {{'name' : '<response>'}}, where <response> is the proposed name
- Use snake_case and a valid Python identifier (letters, digits, underscores; must not start with a digit).
- Be specific to the workflow's purpose; avoid generic names such as "workflow", "graph", or "workflow_graph".

Workflow code:
{code}
"""

NAME_WORKFLOW_CONTEXT_QUERY = ["naming a dispel4py workflow from its processing elements and purpose"]
