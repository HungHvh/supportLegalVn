import os
import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from core.rag_pipeline import LegalRAGPipeline, LegalHybridRetriever
from core.classifier import LegalQueryClassifier
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from retrievers.qdrant_retriever import QdrantRetriever
from llama_index.llms.gemini import Gemini
from dotenv import load_dotenv

# Load environment
load_dotenv()

def run_evaluation():
    """Runs RAGAS evaluation on a small reference dataset."""
    
    # 1. Setup Pipeline
    classifier = LegalQueryClassifier()
    v_retriever = QdrantRetriever()
    f_retriever = SQLiteFTS5Retriever()
    
    hybrid_retriever = LegalHybridRetriever(
        classifier=classifier,
        vector_retriever=v_retriever,
        fts_retriever=f_retriever
    )
    
    llm = Gemini(model="models/gemini-1.5-flash")
    pipeline = LegalRAGPipeline(retriever=hybrid_retriever, llm=llm)

    # 2. Reference Dataset (Small sample for validation)
    eval_data = [
        {
            "question": "Thủ tục thành lập doanh nghiệp tư nhân cần những gì?",
            "ground_truth": "Theo Điều 21 Luật Doanh nghiệp 2020, hồ sơ đăng ký doanh nghiệp tư nhân bao gồm: Giấy đề nghị đăng ký doanh nghiệp, Bản sao giấy tờ pháp lý của cá nhân đối với chủ doanh nghiệp tư nhân."
        },
        {
            "question": "Thời gian giải quyết ly hôn đơn phương là bao lâu?",
            "ground_truth": "Theo Bộ luật Tố tụng dân sự 2015, thời hạn chuẩn bị xét xử vụ án ly hôn là từ 4 đến 6 tháng kể từ ngày thụ lý vụ án."
        }
    ]

    # 3. Generate Answers and Collect Contexts
    results = []
    for item in eval_data:
        question = item["question"]
        print(f"Evaluating: {question}")
        
        # Get response
        response = pipeline.query(question)
        
        # Get retrieved nodes for context metric
        nodes = hybrid_retriever.retrieve(question)
        contexts = [n.node.get_content() for n in nodes]
        
        results.append({
            "question": question,
            "answer": str(response),
            "contexts": contexts,
            "ground_truth": item["ground_truth"]
        })

    # 4. Run RAGAS
    dataset = Dataset.from_pandas(pd.DataFrame(results))
    
    # Note: RAGAS metrics usually require an OpenAI API key by default for the judge.
    # We would need to configure RAGAS to use Gemini as the judge.
    # For now, this script demonstrates the pipeline integration.
    print("\n--- Running RAGAS Metrics ---")
    score = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision]
    )
    
    print("\nEvaluation Scores:")
    print(score)
    
    # Save results
    score.to_pandas().to_csv("eval_results.csv", index=False)
    print("\n[OK] Results saved to eval_results.csv")

if __name__ == "__main__":
    try:
        run_evaluation()
    except Exception as e:
        print(f"\n[Error] Evaluation failed: {e}")
        print("Note: RAGAS evaluation often requires LLM API keys for the judge model.")
