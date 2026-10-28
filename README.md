# Autonomous disproofs of the Erdős unit distance conjecture with GPT-5.5 Pro

This repository contains the scripts and AI-generated transcripts/proofs that accompany the [paper](https://doi.org/10.1073/pnas.2621541123). It presents a simple autonomous agent that robustly and efficiently disproves the Erdős unit distance conjecture using GPT-5.5 Pro.

## Repository Contents

- `unit-distance.pdf`: The paper.
- `run.py`: The core script that interacts with the GPT-5.5 Pro API. It implements a problem-agnostic, three-round prompting pipeline (brainstorm, execute, and review) to autonomously generate proofs.
- `md2html.py`: A utility script for converting math-heavy model outputs into readable HTML using MathJax.
- `outputs/`: A directory containing the outputs from 8 independent trials. Each trial with index `i = 1, 2, ..., 8` includes:
  - `transcript i.html`: The complete conversation log, including all prompts and the model's outputs in all rounds.
  - `proof i.html`: The model's final response containing the proof.
  
  *Note: These files are obtained by converting the math-heavy raw model outputs into a more human-readable format. The conversion is strictly limited to formatting and done via `md2html.py` and a fixed piece of code inside `run.py`. Because GitHub displays HTML files as plain text by default, please download this repository ("Code" > "Download ZIP") and open the `.html` files in your local web browser to view the properly rendered math.*

## How to Run

The core pipeline requires standard Python packages and the official `openai` Python SDK.

To run the agent yourself:

1. Configure your OpenAI API key. You can do this by setting the environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```
   Alternatively, you can enter your API key directly in the `API_KEY` variable near the top of `run.py`.

2. Run the script:
   ```bash
   python run.py
   ```

Running `run.py` produces three files in the `output/` directory:
- `raw_outputs.json`: The full, raw API responses.
- `transcript.html`: The complete conversation log.
- `proof.html`: The model's final response.

*Note: `proof.html` and `transcript.html` use exactly the same formatting as the corresponding HTML files in the repository's `outputs/` directory. Additionally, `run.py` uses a checkpointing system. If the script is interrupted or fails due to network issues, running it again will automatically resume execution from the last completed round without losing progress.*

## Citation

```bibtex
@article{huang2026unitdistance,
  title={Autonomous disproofs of the {Erdős} unit distance conjecture with {GPT-5.5 Pro}},
  author={Yichen Huang},
  journal={Proceedings of the National Academy of Sciences},
  volume={123},
  number={44},
  pages={e2621541123},
  year={2026},
  doi={10.1073/pnas.2621541123}
}
```

## License

Please refer to the `LICENSE` file for detailed licensing information.
