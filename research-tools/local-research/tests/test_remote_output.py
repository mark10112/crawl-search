import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import httpx
from local_research import remote_mcp

def response(data):
    return httpx.Response(200,json=data,request=httpx.Request('GET','http://127.0.0.1/health'))

class RemoteOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_full_read_cannot_be_silently_shortened_by_old_server(self):
        client=SimpleNamespace(get=AsyncMock(return_value=response({})),post=AsyncMock())
        with patch.object(remote_mcp,'client',client):
            with self.assertRaisesRegex(RuntimeError,'does not support complete output'):
                await remote_mcp.post('/jobs',{'url':'https://example.org','max_chars':0})
        client.post.assert_not_awaited()

    async def test_new_server_receives_explicit_full_request(self):
        client=SimpleNamespace(get=AsyncMock(return_value=response({'reader_features':['complete-output-v1']})),
                               post=AsyncMock(return_value=response({'id':'job'})))
        with patch.object(remote_mcp,'client',client):
            self.assertEqual(await remote_mcp.post('/jobs',{'url':'https://example.org','max_chars':0}),{'id':'job'})
        self.assertEqual(client.post.call_args.kwargs['json']['max_chars'],0)

    async def test_existing_preview_reads_remain_compatible(self):
        client=SimpleNamespace(get=AsyncMock(),post=AsyncMock(return_value=response({'id':'job'})))
        with patch.object(remote_mcp,'client',client):
            await remote_mcp.post('/jobs',{'url':'https://example.org','max_chars':22000})
        client.get.assert_not_awaited()
