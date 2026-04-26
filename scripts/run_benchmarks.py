import os
import json
import asyncio
import pandas as pd
import logging
from typing import List, Dict
from dotenv import load_dotenv
from tabulate import tabulate

# LlamaIndex & Pipeline
from llama_index.core import QueryBundle, Settings
from llama_index.llms.gemini import Gemini
from core.rag_pipeline import LegalRAGPipeline, LegalHybridRetriever
from core.classifier import LegalQueryClassifier
from retrievers.qdrant_retriever import QdrantRetriever
from retrievers.sqlite_retriever import SQLiteFTS5Retriever

# Ragas
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from ragas.llms import LangchainLLMWrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from datasets import Dataset

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Config
MANUAL_SET_PATH = ".planning/phases/06-retrieval-evaluation/golden_set_manual.json"
SYNTHETIC_SET_PATH = ".planning/phases/06-retrieval-evaluation/golden_set_synthetic.json"
REPORT_PATH = ".planning/phases/06-retrieval-evaluation/eval_report.md"
CSV_PATH = ".planning/phases/06-retrieval-evaluation/eval_details.csv"

async def setup_pipeline(mode: str = "optimized") -> LegalRAGPipeline:
    """Setup the pipeline in either baseline or optimized mode."""
    classifier = LegalQueryClassifier()
    v_retriever = QdrantRetriever()
    f_retriever = SQLiteFTS5Retriever()
    
    if mode == "baseline":
        # Baseline: Vector only, no classifier
        retriever = LegalHybridRetriever(
            classifier=classifier,
            vector_retriever=v_retriever,
            fts_retriever=f_retriever,
            vector_weight=1.0,
            keyword_weight=0.0,
            use_keyword=False,
            use_classifier=False
        )
    else:
        # Optimized: Hybrid (RRF 50/50), classifier enabled
        retriever = LegalHybridRetriever(
            classifier=classifier,
            vector_retriever=v_retriever,
            fts_retriever=f_retriever,
            vector_weight=0.5,
            keyword_weight=0.5,
            use_keyword=True,
            use_classifier=True
        )
    
    llm = Gemini(model="models/gemini-2.0-flash")
    return LegalRAGPipeline(retriever=retriever, llm=llm)

async def run_evaluation():
    """Main benchmark execution loop."""
    
    # 1. Load Datasets
    logger.info("Loading evaluation datasets...")
    eval_data = []
    if os.path.exists(MANUAL_SET_PATH):
        with open(MANUAL_SET_PATH, "r", encoding="utf-8") as f:
            eval_data.extend(json.load(f))
    
    if not eval_data:
        logger.error("No evaluation data found!")
        return

    # 2. Setup Judge
    logger.info("Configuring Ragas Judge (Gemini 2.0)...")
    gemini_chat = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    ragas_llm = LangchainLLMWrapper(gemini_chat)
    
    # 3. Benchmark Modes
    modes = ["baseline", "optimized"]
    all_results = []

    for mode in modes:
        logger.info(f"--- Running Benchmark: {mode.upper()} ---")
        pipeline = await setup_pipeline(mode=mode)
        
        mode_results = []
        for item in eval_data:
            query = item["query"]
            ground_truth = item.get("reference_answer", "")
            
            logger.info(f"Querying: {query}")
            try:
                # Get response
                response_data = await pipeline.acustom_query(query)
                answer = response_data["answer"]
                
                # Get retrieved nodes for context metrics
                nodes = await pipeline.retriever.aretrieve(query)
                contexts = [n.node.get_content() for n in nodes]
                
                mode_results.append({
                    "question": query,
                    "answer": answer,
                    "contexts": contexts,
                    "ground_truth": ground_truth,
                    "mode": mode
                })
            except Exception as e:
                logger.error(f"Error evaluating query '{query}': {e}")

        # Convert to Ragas Dataset
        dataset = Dataset.from_pandas(pd.DataFrame(mode_results))
        
        logger.info(f"Scoring {mode} results with Ragas...")
        scores = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision],
            llm=ragas_llm
        )
        
        df_scores = scores.to_pandas()
        df_scores["mode"] = mode
        all_results.append(df_scores)

    # 4. Process Results
    final_df = pd.concat(all_results)
    final_df.to_csv(CSV_PATH, index=False)
    
    # Aggregate Metrics
    summary = final_df.groupby("mode")[["faithfulness", "answer_relevancy", "context_precision"]].mean()
    
    # 5. Generate Report
    report = f"""# Retrieval Evaluation Report (Phase 6)

## Summary Metrics
{summary.to_markdown()}

## Detailed Comparison
"""
    # Add some sample query comparisons
    for query in eval_data[:3]:
        q_text = query["query"]
        report += f"\n### Query: {q_text}\n"
        
        q_results = final_df[final_df["question"] == q_text]
        for _, row in q_results.iterrows():
            report += f"**Mode: {row['mode']}**\n"
            report += f"- Faithfulness: {row['faithfulness']:.2f}\n"
            report += f"- Answer: {row['answer'][:200]}...\n\n"

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    
    logger.info(f"Evaluation complete. Report saved to {REPORT_PATH}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
