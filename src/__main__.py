"""
CLI Chatbot — chạy RAG pipeline end-to-end qua terminal.

Chạy:
    python -m src
    python -m src --top-k 3 --retrieval-mode dense --no-rerank --rerank-method mmr
"""

import argparse
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .task10_generation import generate_with_citation, generate_with_citation_stream, TOP_K


def main():
    parser = argparse.ArgumentParser(description="RAG CLI Chatbot")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--retrieval-mode", choices=["dense", "hybrid"], default="hybrid")
    parser.add_argument("--no-rerank", action="store_true", help="Disable reranking")
    parser.add_argument("--rerank-method", choices=["cross_encoder", "mmr"], default="cross_encoder")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming, wait for full answer")
    args = parser.parse_args()

    print("RAG Chatbot — gõ câu hỏi, Ctrl+C hoặc 'exit' để thoát.")
    print(f"[retrieval_mode={args.retrieval_mode} rerank={'off' if args.no_rerank else args.rerank_method} top_k={args.top_k} stream={not args.no_stream}]\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            print("Bye.")
            break

        try:
            if args.no_stream:
                result = generate_with_citation(
                    query,
                    top_k=args.top_k,
                    retrieval_mode=args.retrieval_mode,
                    use_reranking=not args.no_rerank,
                    rerank_method=args.rerank_method,
                )
                print(f"\nBot: {result['answer']}")
                print(f"[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]\n")
            else:
                print("\nBot: ", end="", flush=True)
                sources_count = 0
                retrieval_source = "none"
                for event in generate_with_citation_stream(
                    query,
                    top_k=args.top_k,
                    retrieval_mode=args.retrieval_mode,
                    use_reranking=not args.no_rerank,
                    rerank_method=args.rerank_method,
                ):
                    if event["type"] == "delta":
                        print(event["content"], end="", flush=True)
                    else:
                        sources_count = len(event["sources"])
                        retrieval_source = event["retrieval_source"]
                print(f"\n[Sources: {sources_count} chunks | via {retrieval_source}]\n")
        except Exception as e:
            print(f"[Error] {e}\n")
            continue


if __name__ == "__main__":
    main()
