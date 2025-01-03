import os
import operator
from typing import Annotated, Any
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import ConfigurableField
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
import yaml
import logging
import re

# Logging configuration
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# State class
class State(BaseModel):
    query: str = Field(..., description="Workflow content that the user wants to generate")
    messages: Annotated[list[str], operator.add] = Field(
        default=[], description="Response history"
    )
    current_judge: bool = Field(default=False, description="Quality check result")
    judgement_reason: str = Field(default="", description="Quality check judgment reason")
    operator_approved: bool = Field(default=False, description="Operator approval status")

class Judgement(BaseModel):
    reason: str = Field(default="", description="Judgment reason")
    judge: bool = Field(default=False, description="Judgment result")

class WorkflowGenerator:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0.0)
        self.llm = self.llm.configurable_fields(max_tokens=ConfigurableField(id='max_tokens'))

    def load_prompt(self, file_path: str) -> dict:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def generate_workflow(self, state: State) -> dict[str, Any]:
        logging.info("workflow_generator_node: START")
        query = state.query
        role = "You are an expert in generating Dify workflows."
        role_details = self.load_prompt("workflow_generator_prompt.yml")

        # Create a prompt including the reason if there were issues in the previous check
        if state.judgement_reason:
            prompt = ChatPromptTemplate.from_template(
                """{role_details}{query}
                The following issues were detected in the previous generation, please fix them:
                {judgement_reason}""".strip()
            )
        else:
            prompt = ChatPromptTemplate.from_template(
                """{role_details}{query}""".strip()
            )
        chain = prompt | self.llm.with_config({"max_tokens": 8192}) | StrOutputParser()
        answer = self._get_complete_answer(chain, role, role_details, query, state.judgement_reason)
        
        logging.info("workflow_generator_node: END")
        return {"messages": [answer]}

    def _get_complete_answer(self, chain, role, role_details, query, judgement_reason=""):
        answer = ""
        while True:
            try:
                current_answer = chain.invoke({
                    "role": role, 
                    "role_details": role_details,
                    "query": query + ("\nExisting answer:" + answer if answer else ""),
                    "judgement_reason": judgement_reason
                })
                answer += current_answer
                break
            except Exception as e:
                if "maximum context length" not in str(e):
                    raise e
        return answer

    def check_workflow(self, state: State) -> dict[str, Any]:
        logging.info("check_node: START")
        answer = state.messages[-1]
        prompt_data = self.load_prompt("workflow_generator_prompt.yml")
        
        prompt = ChatPromptTemplate.from_template(
            """
            Please check if the generated workflow follows the rules specified in the prompt.
            Answer 'False' if there are issues, 'True' if there are no issues.
            Also, please explain the reason for your judgment.
            Prompt: {prompt_data}
            Answer: {answer}
            """
        )

        chain = prompt | self.llm.with_structured_output(Judgement)
        result: Judgement = chain.invoke({
            "query": state.query, 
            "answer": answer,
            "prompt_data": prompt_data
        })

        logging.info(f"check_node: END {'with error' if not result.judge else ''}")
        return {
            "current_judge": result.judge,
            "judgement_reason": result.reason
        }

def ask_operator(state: State) -> dict[str, Any]:
    logging.info("Checking with operator...")
    print(f"\nWarning: The following issues were detected:\n{state.judgement_reason}")
    print("\nGenerated workflow:")
    print(state.messages[-1])
    
    while True:
        response = input("\nDo you want to regenerate this workflow? (y/n): ").lower()
        if response == 'y':
            return {"operator_approved": False}
        elif response == 'n':
            return {"operator_approved": True}
        else:
            print("Invalid input. Please enter y or n.")

def create_workflow_graph(generator: WorkflowGenerator) -> StateGraph:
    workflow = StateGraph(State)
    
    workflow.add_node("workflow_generator", generator.generate_workflow)
    workflow.add_node("check", generator.check_workflow)
    workflow.add_node("ask_operator", ask_operator)
    
    workflow.set_entry_point("workflow_generator")
    workflow.add_edge("workflow_generator", "check")
    
    workflow.add_conditional_edges(
        "check",
        lambda state: state.current_judge,
        {True: END, False: "ask_operator"}
    )

    workflow.add_conditional_edges(
        "ask_operator",
        lambda state: state.operator_approved,
        {True: END, False: "workflow_generator"}
    )

    return workflow.compile()


def main():
    setup_logging()
    
    wanted_workflow = """
    Purpose: Research and create an article about cooking recipes
    1. Search the internet for cooking recipes and get 3 URLs
    2. Retrieve information from the 3 URLs
    3. Input the information obtained from the 3 URLs into LLM and organize the cooking recipe for output
    """
    
    generator = WorkflowGenerator()
    workflow = create_workflow_graph(generator)
    
    initial_state = State(query=wanted_workflow)
    result = workflow.invoke(initial_state)
    
    logging.info(f"Judgment: {result['current_judge']}")
    logging.info(f"Judgment reason: {result['judgement_reason']}")
    # Extract the part enclosed by ```yaml and ``` from the message
    yaml_content = re.search(r'```yaml\n(.*?)```', result['messages'][-1], re.DOTALL)
    if yaml_content:
        logging.info(f"Result: \n {yaml_content.group(1)}")
    else:
        logging.error("YAML content not found.")

if __name__ == "__main__":
    main()
