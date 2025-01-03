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

# 日志配置
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# 状态类
class State(BaseModel):
    query: str = Field(..., description="用户想要生成的工作流内容")
    messages: Annotated[list[str], operator.add] = Field(
        default=[], description="响应历史记录"
    )
    current_judge: bool = Field(default=False, description="质量检查结果")
    judgement_reason: str = Field(default="", description="质量检查判断原因")
    operator_approved: bool = Field(default=False, description="操作员审批状态")

class Judgement(BaseModel):
    reason: str = Field(default="", description="判断原因")
    judge: bool = Field(default=False, description="判断结果")

class WorkflowGenerator:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0.0)
        self.llm = self.llm.configurable_fields(max_tokens=ConfigurableField(id='max_tokens'))

    def load_prompt(self, file_path: str) -> dict:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def generate_workflow(self, state: State) -> dict[str, Any]:
        logging.info("工作流生成节点：开始")
        query = state.query
        role = "您是生成Dify工作流的专家。"
        role_details = self.load_prompt("workflow_generator_prompt.yml")

        # 如果之前的检查中存在问题，则创建包含原因的提示
        if state.judgement_reason:
            prompt = ChatPromptTemplate.from_template(
                """{role_details}{query}
                在上一次生成中检测到以下问题，请修复：
                {judgement_reason}""".strip()
            )
        else:
            prompt = ChatPromptTemplate.from_template(
                """{role_details}{query}""".strip()
            )
        chain = prompt | self.llm.with_config({"max_tokens": 8192}) | StrOutputParser()
        answer = self._get_complete_answer(chain, role, role_details, query, state.judgement_reason)
        
        logging.info("工作流生成节点：结束")
        return {"messages": [answer]}

    def _get_complete_answer(self, chain, role, role_details, query, judgement_reason=""):
        answer = ""
        while True:
            try:
                current_answer = chain.invoke({
                    "role": role, 
                    "role_details": role_details,
                    "query": query + ("\n现有答案:" + answer if answer else ""),
                    "judgement_reason": judgement_reason
                })
                answer += current_answer
                break
            except Exception as e:
                if "maximum context length" not in str(e):
                    raise e
        return answer

    def check_workflow(self, state: State) -> dict[str, Any]:
        logging.info("检查节点：开始")
        answer = state.messages[-1]
        prompt_data = self.load_prompt("workflow_generator_prompt.yml")
        
        prompt = ChatPromptTemplate.from_template(
            """
            请检查生成的工作流是否遵循提示中指定的规则。
            如果存在问题，请回答'False'，如果没有问题，请回答'True'。
            同时，请解释您的判断原因。
            提示：{prompt_data}
            回答：{answer}
            """
        )

        chain = prompt | self.llm.with_structured_output(Judgement)
        result: Judgement = chain.invoke({
            "query": state.query, 
            "answer": answer,
            "prompt_data": prompt_data
        })

        logging.info(f"检查节点：结束 {'有错误' if not result.judge else ''}")
        return {
            "current_judge": result.judge,
            "judgement_reason": result.reason
        }

def ask_operator(state: State) -> dict[str, Any]:
    logging.info("正在与操作员确认...")
    print(f"\n警告：检测到以下问题：\n{state.judgement_reason}")
    print("\n生成的工作流：")
    print(state.messages[-1])
    
    while True:
        response = input("\n您想要重新生成这个工作流吗？(y/n)：").lower()
        if response == 'y':
            return {"operator_approved": False}
        elif response == 'n':
            return {"operator_approved": True}
        else:
            print("无效输入。请输入 y 或 n。")

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
    目的：研究并创建一篇关于烹饪食谱的文章
    1. 在互联网上搜索烹饪食谱并获取3个URL
    2. 从这3个URL中获取信息
    3. 将从3个URL获得的信息输入到LLM中，整理烹饪食谱并输出
    """
    
    generator = WorkflowGenerator()
    workflow = create_workflow_graph(generator)
    
    initial_state = State(query=wanted_workflow)
    result = workflow.invoke(initial_state)
    
    logging.info(f"判断：{result['current_judge']}")
    logging.info(f"判断原因：{result['judgement_reason']}")
    # 从消息中提取被```yaml和```包围的部分
    yaml_content = re.search(r'```yaml\n(.*?)```', result['messages'][-1], re.DOTALL)
    if yaml_content:
        logging.info(f"结果：\n {yaml_content.group(1)}")
    else:
        logging.error("未找到YAML内容。")

if __name__ == "__main__":
    main()
