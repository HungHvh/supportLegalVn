# Phase 6 Research: Retrieval Evaluation

## Standard Stack
- **Evaluation Framework**: [Ragas](https://docs.ragas.io/) (v0.1.x+)
- **Dataset Generation**: `llama-index-core` (`RagDatasetGenerator`)
- **LLM Judge**: `gemini-2.0-flash` (via `langchain-google-genai` wrapper)
- **Data Analysis**: `pandas` & `tabulate` (for Markdown reports)

## ⚠️ Environment Notes & Workarounds

### Local Environment Issues (Windows 2026)
- **DLL Initialization Errors**: Attempting to run evaluation scripts locally resulted in `WinError 1114` when loading `torch/lib/c10.dll` and `onnxruntime_pybind11_state`. 
- **Impact**: Scripts using `llama-index` (embeddings), `spacy` (node postprocessing), or `fastembed` fail to initialize.

### Docker Solution
- **Strategy**: All Phase 6 evaluation tasks are moved to Docker execution using the `api` image.
- **Workflow**:
    1. Build image: `docker-compose build api`
    2. Run Benchmarks: `docker-compose run api python scripts/run_benchmarks.py`
- **Benefits**: Consistent Linux-based environment (Python 3.12-slim) with all system dependencies pre-installed.

### Quota Management
- **Gemini 2.0 Flash**: High RPM limits observed on free tier. Retry logic with exponential backoff implemented in `generate_eval_data.py`.

## Architecture Patterns

### 1. The Evaluation Loop
The evaluation will follow a three-stage pipeline:
1.  **Generation**: Scan the `legal_poc.db` (Enterprise Law domain) and generate 30-40 synthetic query triplets.
2.  **Execution**: Run the `LegalRAGPipeline` twice for each query (Baseline vs. Optimized) and store the results.
3.  **Scoring**: Batch process the results through Ragas to calculate Faithfulness, Relevance, and Precision.

### 2. Ablation Configuration (The "Baseline" Simulation)
To avoid the complexity of maintaining two separate indices, the "Baseline" will be simulated by passing a `config` object to the retriever:
- **Baseline**: `vector_weight=1.0`, `keyword_weight=0.0` (Vector only), `use_classifier=False`.
- **Optimized**: `vector_weight=0.5`, `keyword_weight=0.5` (RRF), `use_classifier=True`.

## Don't Hand-Roll
- **Metric Calculations**: Do not write custom logic for Faithfulness or MRR. Use Ragas and LlamaIndex's built-in evaluators.
- **Judge Prompts**: Use the battle-tested prompts provided by Ragas for the LLM judge.

## Common Pitfalls
- **Rate Limiting**: Ragas runs evaluations in parallel by default. We must set `max_workers` or `rate_limit` to avoid hitting Gemini API quotas during batch scoring.
- **Context Mismatch**: Ensure the "Ground Truth" context in the synthetic dataset matches the expected retrieval unit (chunks) to ensure fair Hit Rate @ K scoring.

## Code Examples

### Configuring Gemini as Ragas Judge
```python
from langchain_google_genai import ChatGoogleGenerativeAI
from ragas.llms import LangchainLLMWrapper
from ragas import evaluate

# Initialize Gemini
gemini_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
ragas_judge = LangchainLLMWrapper(gemini_llm)

# Run evaluation
results = evaluate(
    dataset=eval_dataset,
    metrics=[faithfulness, answer_relevancy],
    llm=ragas_judge
)
```
