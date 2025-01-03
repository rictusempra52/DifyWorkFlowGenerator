# Dify Workflow Generator Prompt

## Overview

This repository provides prompt definitions for generating workflows in [Dify](https://dify.ai). Following detailed prompt specifications written in YAML format, you can create workflows for various use cases.

## Features

- Simple workflow generation using three basic nodes (Start, LLM, End)
- Support for advanced node types:
  - Question Classifier
  - Knowledge Retrieval
  - HTTP Request
  - JSON Parser
  - IF/ELSE Node
  - Code Node
  - Variable Aggregator Node

## File Contents

- workflow_generator_prompt.yml
  - Definition of workflow generation prompts
- dify_chatbot/DifyWorkflowGeneate.yml
  - Dify chatbot with workflow_generator_prompt.yml applied
- example/manual_search.yml
  - Example of workflow generation

## Usage

1. Clone the repository:
```
https://github.com/Tomatio13/DifyWorkFlowGenerator.git
```
2. Import the workflow generation prompt dify_chatbot/DifyWorkflowGeneate.yml into Dify.
After importing, you will see a screen like this:
![Dify Workflow Generator](./images/DifyWorkflowGenerator_initial.jpg)

*Note*: Please run this prompt with claude-3-5-sonnet, not gpt-4o. Workflows will not be generated correctly with gpt-4o.

3. Prepare necessary information:
   - Purpose of the workflow
   - If using knowledge control blocks, look up the dataset_ids:
        - How to find them:
            Create a workflow that includes knowledge.
            Export the DSL of the created workflow.
            ```yml
            type: knowledge-retrieval
            title: Ubuntu Knowledge Retrieval
            dataset_ids:
                - 84782981-6a4d-4d19-9189-dd72fe435a57
            retrieval_mode: multiple
            ```
            Note down the dataset_ids as shown above.

4. Create and execute the prompt as shown in the image below:
![Dify Workflow Generator](./images/DifyWorkflowGenerator.jpg)
A YAML file that can be imported into Dify will be generated as shown in the figure.
5. Copy the generated YAML to a separate file and import it into Dify.
6. Below is a screen showing example/manual_search.yml after import:
![Dify Workflow Generator](./images/manual_search.jpg)

## Sample
example/adviser_bot.yml
  - Workflow utilizing question classifier, knowledge retrieval, IF/ELSE branching, template transformation, and parameter extraction
![Workflow Image](./images/adviser_bot.png)

## Supported Node Types

### Basic Nodes
- Start Node: Accepts user input
  - Text input (short text/paragraph)
  - Numeric input
  - File input (documents, images, audio, video)
- LLM Node: Processing using OpenAI GPT-4
- End Node: Output results

### Extended Nodes
- HTTP Request Node: External API integration
- JSON Parse Node: JSON processing
- Question Classifier Node: Input classification
- Knowledge Retrieval Node: Information search from datasets
- IF/ELSE Node: Conditional branching
- Code Node: Python code execution
- Variable Aggregator Node: Aggregates output from multiple nodes
- Document Extractor Node: Text extraction from documents
- Template Transform Node: Template-based string generation
- Answer Node: Response output control
- Parameter Extractor Node: Parameter extraction from text
- YouTube Transcript Node: YouTube video subtitle retrieval
- JinaReader Node: Web page content extraction
- TavilySearch Node: Web search execution

## Workflow Examples

### Simple Processing Flow
```yaml
Start → LLM → End
```

### Flow with Branching
```yaml
Start → Question Classifier → Knowledge Retrieval → LLM → End
                          → Knowledge Retrieval → LLM → End
```

### IF/ELSE Branching Flow
```yaml
Start → IF/ELSE → LLM(True) → End
               → LLM(False) → End
```

### Variable Aggregation Flow
```yaml
Start → LLM1 → Variable Aggregator → End
      → LLM2 ↗
```

### Document Processing Flow
```yaml
Start(File Input) → Document Extractor → LLM → End
```

### Template Transformation Flow
```yaml
Start → Template Transform → LLM → End
```

### Complex Processing Flow
```yaml
Start(File) → Document Extractor → Template Transform → LLM → End
```

### Response Control Flow
```yaml
Start → LLM → Answer → End
```

### Complex Response Flow
```yaml
Start → LLM1 → Template Transform → Answer → End
      → LLM2 ↗
```

### Parameter Extraction Flow
```yaml
Start → Parameter Extractor → LLM → End
```

### Complex Parameter Processing Flow
```yaml
Start → Parameter Extractor → Template Transform → Answer → End
```

### YouTube Transcript Flow
```yaml
Start → YouTube Transcript → LLM → End
```

### Web Content Processing Flow
```yaml
Start → JinaReader → LLM → End
```

### Web Search Flow
```yaml
Start → TavilySearch → LLM → End
```

### Complex Media Processing Flow
```yaml
Start → YouTube Transcript → Template Transform → LLM → End
      → JinaReader → ↗
```

## Limitations

- Only supports OpenAI's gpt-4o model (change model settings on the Dify screen)
- Boolean type not available in code nodes (use 0/1 with number type)
- File input supports only the following formats:
  - Documents (PDF, Word, etc.)
  - Images (JPG, PNG, etc.)
  - Audio (MP3, WAV, etc.)
  - Video (MP4, etc.)
- Template Transform Node constraints:
  - Output is always string type
  - Only supports Jinja2 template syntax
  - Complex control syntax not recommended
- Answer Node constraints:
  - arrayObject type variables not supported
  - Special behavior in chat mode
  - Variable references only in {{#nodeID.variableName#}} format
- Parameter Extractor Node constraints:
  - Parameter names must be unique
  - Required parameters must be extracted
  - Image processing only available with supported models
  - Inference mode limited to prompt or function_call
- Unsupported nodes:
  - Iteration nodes
  - Variable assignment nodes
  - List processing
  - Tool nodes in general
- YouTube Transcript Node constraints:
  - Only supports public videos
  - Only works with videos that have subtitles
  - Requires subtitles in specified language
- JinaReader Node constraints:
  - Only supports accessible web pages
  - JavaScript dynamic content may not be fully retrieved
  - May require proxy settings
- TavilySearch Node constraints:
  - Limited number of search results (max 10)
  - Possible access restrictions for some domains
  - Processing time varies with search depth

## About difyDslGenCheck.py
*Note*: This is an experimental feature and may often fail to generate workflows. Please use Dify's workflow generation feature instead.
### Features
- Generates DSL files based on workflow overview
- Checks if the generated DSL file structure is correct
- Modifies DSL files based on check results

### Usage
1. Describe the overview of the workflow you want to generate in difyDslGenCheck.py:

```python
    wanted_workflow = """
    Prompt:
    Purpose: A tool to research destination information like a travel concierge
    1. Get input of destination name as input information.
    2. Search the internet and obtain 3 URLs containing tourist and gourmet information about the destination.
    3. Retrieve information from the 3 URLs. Process the 3 URLs in parallel.
    4. Input the information obtained from the 3 URLs to LLM, organize the destination information, and output it. The output should be formatted as an article suitable for publication in a travel magazine.
    """
```
2. Execute the script:
```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key"
python -m venv dify_env
source dify_env/bin/activate
pip install -r requirements.txt
python difyDslGenCheck_en.py
```

## License

MIT License

## Contributing

Pull requests and issue reports are welcome.

## Related Links

- [Dify Official Website](https://dify.ai)
- [Dify Documentation](https://docs.dify.ai) 