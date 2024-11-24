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

# ロギング設定
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# 状態クラス
class State(BaseModel):
    query: str = Field(..., description="ユーザが生成したいワークフローの内容")
    messages: Annotated[list[str], operator.add] = Field(
        default=[], description="回答履歴"
    )
    current_judge: bool = Field(default=False, description="品質チェックの結果")
    judgement_reason: str = Field(default="", description="品質チェックの判定理由")

class Judgement(BaseModel):
    reason: str = Field(default="", description="判定理由")
    judge: bool = Field(default=False, description="判定結果")

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
        role = "あなたはDifyのワークフローを生成するエキスパートです。"
        role_details = self.load_prompt("workflow_generator_prompt.yml")

        # 前回のチェックで問題があった場合、その理由を含めたプロンプトを作成
        if state.judgement_reason:
            prompt = ChatPromptTemplate.from_template(
                """プロンプト:{role_details}を元に、ワークフローを生成して下さい。
                前回の生成で以下の問題が検出されました：
                {judgement_reason}
                
                この問題を修正したワークフローを生成してください。
                出力はYAML形式です。YAML以外は出力しないで下さい。
                
                質問: {query}
                回答:""".strip()
            )
        else:
            # 初回生成時の既存のプロンプト
            prompt = ChatPromptTemplate.from_template(
                """プロンプト:{role_details}を元に、ワークフローを生成して下さい。出力はYAML形式です。YAML以外は出力しないで下さい。
                質問: {query}
                回答:""".strip()
            )

        chain = prompt | self.llm.with_config({"max_tokens": 4000}) | StrOutputParser()
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
                    "query": query + ("\n既存の回答:" + answer if answer else ""),
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
            生成されたワークフローがプロンプトに記載されているルールに従っているかをチェックして下さい。
            問題がある場合は'False'、問題がない場合は'True'を回答して下さい。
            また、その判断理由も説明して下さい。
            プロンプト:{prompt_data}
            回答: {answer}
            """.strip()
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

def create_workflow_graph(generator: WorkflowGenerator) -> StateGraph:
    workflow = StateGraph(State)
    
    workflow.add_node("workflow_generator", generator.generate_workflow)
    workflow.add_node("check", generator.check_workflow)
    
    workflow.set_entry_point("workflow_generator")
    workflow.add_edge("workflow_generator", "check")
    
    workflow.add_conditional_edges(
        "check",
        lambda state: state.current_judge,
        {True: END, False: "workflow_generator"}
    )
    
    return workflow.compile()

def main():
    setup_logging()
    
    wanted_workflow = """
    プロンプト：
    目的：旅行コンシェルジェのように旅行先の目的地の情報を調査するためのツール
    1. 入力情報として、旅行先の地名を入力してもらう。
    2. インターネットを検索し、旅行先の観光情報やグルメ情報が書かれたURLを3つ入手する。
    3. 3つのURLから情報を取得する。3つは並列に処理すること。
    4. 3つのURLから得た情報をLLに入力し、良好先の情報を整理して出力する。出力は、旅行情報雑誌に掲載できる文章に仕上げること。
    """
    
    generator = WorkflowGenerator()
    workflow = create_workflow_graph(generator)
    
    initial_state = State(query=wanted_workflow)
    result = workflow.invoke(initial_state)
    
    logging.info(f"判定: {result['current_judge']}")
    logging.info(f"判定理由: {result['judgement_reason']}")
    logging.info(f"結果: {result['messages'][-1]}")

if __name__ == "__main__":
    main()
