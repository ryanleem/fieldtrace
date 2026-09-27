"""Mocked provider diagnostics: no live calls, prompts, or credentials in logs."""
import json
import logging
import httpx
import pytest
from app.config import Settings
from app.services.troubleshooting_provider import OpenAITroubleshootingProvider, TroubleshootingUnavailable

KEY = 'sk-private-test-credential'
LOGGER = 'app.services.troubleshooting_provider'


def invoke(response):
    provider = OpenAITroubleshootingProvider(Settings(openai_api_key=KEY),
        httpx.MockTransport(lambda request: response))
    with pytest.raises(TroubleshootingUnavailable) as exc:
        provider.complete('verify', {'claim': 'PRIVATE technician observation', 'evidence': []})
    assert str(exc.value) == 'Troubleshooting provider failed or returned incomplete output'
    assert exc.value.__suppress_context__


@pytest.mark.parametrize('status,code,message,expected', [
    (429,'rate_limit_exceeded','Rate limit reached for model on tokens per min (TPM): Limit 30000, Used 29500, Requested 800. Try again in 2s.','tokens per min (TPM)'),
    (429,'rate_limit_exceeded','Rate limit reached on requests per min (RPM): Limit 20.','requests per min (RPM)'),
    (429,'insufficient_quota','You exceeded your current quota, please check your plan and billing details.','exceeded your current quota'),
    (429,'credit_balance_exhausted','Credit balance exhausted; project limit.','project limit'),
    (404,'model_not_found','The model does not exist or you do not have access to it.','do not have access'),
    (500,'server_error','Internal server error.','Internal server error'),
])
def test_http_failure_logs_diagnostic_fields(caplog,status,code,message,expected):
    with caplog.at_level(logging.WARNING,logger=LOGGER):
        invoke(httpx.Response(status,json={'error':{'type':'invalid_request_error','code':code,'message':message,'param':'model'}},headers={'x-request-id':'req_diagnostic123'}))
    records=[r for r in caplog.records if r.name==LOGGER]
    assert len(records)==1 and records[0].exc_info is None
    diagnostic=json.loads(records[0].getMessage().split(': ',1)[1])
    assert diagnostic['stage']=='verify' and diagnostic['http_status']==status
    assert diagnostic['request_id']=='req_diagnostic123'
    assert diagnostic['error']['code']==code and diagnostic['error']['type']=='invalid_request_error'
    assert diagnostic['error']['param']=='model' and expected in diagnostic['error']['message']
    assert KEY not in caplog.text and 'Authorization' not in caplog.text
    assert 'PRIVATE technician observation' not in caplog.text


def test_error_echoes_headers_credentials_and_user_text_are_not_logged(caplog):
    error={'type':KEY,'code':'server_error','param':'Authorization: Bearer '+KEY,
        'message':'Internal server error. Authorization: Bearer '+KEY+' PRIVATE technician observation; arbitrary sensitive echo',
        'input':'PRIVATE technician observation','request_headers':{'Authorization':'Bearer '+KEY}}
    with caplog.at_level(logging.WARNING,logger=LOGGER):
        invoke(httpx.Response(500,json={'error':error,'input':'PRIVATE technician observation'},headers={'x-request-id':KEY}))
    assert 'Internal server error' in caplog.text
    for private in [KEY,'Authorization','Bearer','PRIVATE','arbitrary sensitive echo','request_headers']:
        assert private not in caplog.text


@pytest.mark.parametrize('body', [b'<html>Authorization: secret PRIVATE</html>',b'{broken',b'[]',b'{"error":"PRIVATE"}',b'{"error":{"message":{"secret":"PRIVATE"},"code":["PRIVATE"]}}'])
def test_malformed_or_unstructured_error_body_is_not_dumped(caplog,body):
    with caplog.at_level(logging.WARNING,logger=LOGGER):invoke(httpx.Response(500,content=body))
    assert 'http_status' in caplog.text
    assert 'PRIVATE' not in caplog.text and 'Authorization' not in caplog.text


def test_network_failure_remains_generic_and_does_not_log_exception(caplog):
    def fail(request):raise httpx.ConnectError('Authorization '+KEY+' PRIVATE',request=request)
    provider=OpenAITroubleshootingProvider(Settings(openai_api_key=KEY),httpx.MockTransport(fail))
    with pytest.raises(TroubleshootingUnavailable):provider.complete('verify',{})
    assert KEY not in caplog.text and not [r for r in caplog.records if r.name==LOGGER]


def test_success_output_and_raw_payload_unchanged(caplog):
    output={'status':'SUPPORTED','explanation':'Fixture','revised_text':None}
    raw={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(output)}]}]}
    provider=OpenAITroubleshootingProvider(Settings(openai_api_key=KEY),httpx.MockTransport(lambda _:httpx.Response(200,json=raw)))
    assert provider.complete('verify',{})=={'output':output,'raw':raw}
    assert not [r for r in caplog.records if r.name==LOGGER]
