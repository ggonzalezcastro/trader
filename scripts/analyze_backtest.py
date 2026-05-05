#!/usr/bin/env python3
"""
CLI tool: Analyze MT5 backtest results with AI.

Usage:
    python scripts/analyze_backtest.py report.html
    python scripts/analyze_backtest.py report.html --provider anthropic --model claude-3-5-sonnet
    python scripts/analyze_backtest.py report.html --provider openai --model gpt-4-turbo --api-key sk-...
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.backtest_analyst import BacktestAnalyst, quick_analyze
from services.analyst import ModelConfig

def main():
    parser = argparse.ArgumentParser(description="Analyze MT5 backtest with AI")
    parser.add_argument("file", help="MT5 report file (HTML, XML, CSV)")
    parser.add_argument("--provider", "-p", default="openai",
                       choices=["openai", "anthropic", "minimax", "deepseek", "ollama", "mock"],
                       help="AI provider (default: openai)")
    parser.add_argument("--model", "-m", default=None,
                       help="Model name (default varies by provider)")
    parser.add_argument("--api-key", "-k", default=None,
                       help="API key (or set env var)")
    parser.add_argument("--output", "-o", default=None,
                       help="Save result to JSON file")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    # Model defaults by provider
    model_map = {
        "openai": "gpt-4",
        "anthropic": "claude-3-5-sonnet-20241022",
        "minimax": "MiniMax-Text-01",
        "deepseek": "deepseek-chat",
        "ollama": "llama3.2",
        "mock": "mock"
    }
    model = args.model or model_map.get(args.provider, "gpt-4")
    
    # API key from args or env
    api_key = args.api_key
    if not api_key:
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY"
        }
        api_key = os.getenv(env_map.get(args.provider, ""), "")
    
    if args.verbose:
        print(f"Provider: {args.provider}")
        print(f"Model: {model}")
        print(f"File: {args.file}")
        print(f"API Key: {'set' if api_key else 'NOT SET (using mock)'}")
        print()
    
    # Run analysis
    print("Analyzing backtest report...")
    try:
        config = ModelConfig(
            provider=args.provider,
            model=model,
            api_key=api_key or None
        )
        analyst = BacktestAnalyst(config)
        result = analyst.analyze_file(args.file)
        
        # Print results
        print("\n" + "="*60)
        print("ANALYSIS RESULTS")
        print("="*60)
        print(f"\nSummary: {result.summary}")
        print(f"\nTrades analyzed: {result.trades_analyzed}")
        print(f"Win rate: {result.win_rate}%")
        print(f"Profit factor: {result.profit_factor}")
        
        if result.issues_found:
            print(f"\nIssues found ({len(result.issues_found)}):")
            for i, issue in enumerate(result.issues_found, 1):
                print(f"  {i}. {issue}")
        
        if result.suggestions:
            print(f"\nSuggestions ({len(result.suggestions)}):")
            for i, sug in enumerate(result.suggestions, 1):
                print(f"  {i}. {sug}")
        
        print("\n" + "-"*60)
        print("FULL AI RESPONSE:")
        print("-"*60)
        print(result.raw_response or "No response")
        
        # Save to file if requested
        if args.output:
            import json
            output_data = {
                "file": str(args.file),
                "provider": args.provider,
                "model": model,
                "result": {
                    "summary": result.summary,
                    "trades_analyzed": result.trades_analyzed,
                    "win_rate": result.win_rate,
                    "profit_factor": result.profit_factor,
                    "issues_found": result.issues_found,
                    "suggestions": result.suggestions,
                    "raw_response": result.raw_response
                }
            }
            Path(args.output).write_text(json.dumps(output_data, indent=2))
            print(f"\nResult saved to: {args.output}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
