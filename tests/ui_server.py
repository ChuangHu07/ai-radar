"""Isolated browser test on port 8001; synthetic provider, no API requests or charges."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import create_app
from app.reading.reports import generate_single
from test_reading import FakeProvider


async def synthetic_report(data, material, usage, phase):
    class BrowserProvider(FakeProvider):
        async def format(self, system, messages, schema):
            response = await super().format(system, messages, schema)
            import json
            output = json.loads(response.content[0].text)
            output["material_id"] = material["material_id"]
            response.content[0].text = json.dumps(output, ensure_ascii=False)
            return response
    return await generate_single(data, material, usage, phase, BrowserProvider)


app = create_app(generate=synthetic_report)
