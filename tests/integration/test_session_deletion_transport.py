"""Real HTTP/WS deletion, including an already-connected subscription."""
import unittest
from unittest.mock import patch
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
import test_transport as transport_fixture


class SessionDeletionTransportTests(unittest.TestCase):
    setUp=transport_fixture.TransportTests.setUp
    tearDown=transport_fixture.TransportTests.tearDown
    request=transport_fixture.TransportTests.request
    setup_session=transport_fixture.TransportTests.setup_session

    def test_delete_http_and_active_socket_close_with_no_resurrection(self):
        snapshot=self.setup_session();sid=snapshot["session_id"];route=f"/v1/sessions/{sid}"
        with connect(f"ws://127.0.0.1:{self.port}"+route+"/events?after_sequence=0",origin=self.origin,close_timeout=1) as ws:
            status,deleted=self.request("DELETE",route)
            self.assertEqual(200,status);self.assertEqual(dict(session_id=sid,deleted=True),deleted)
            with self.assertRaises(ConnectionClosed) as error:
                while True:ws.recv(timeout=2)
            self.assertEqual(4404,error.exception.rcvd.code)
            self.assertEqual("unknown_session",error.exception.rcvd.reason)
        self.assertEqual((200,deleted),self.request("DELETE",route))
        self.assertEqual(404,self.request("GET",route)[0])
        self.assertEqual(404,self.request("POST",route+"/actions",json_body={})[0])
        self.assertEqual(200,self.request("DELETE","/v1/sessions/not-present")[0])

    def test_foreign_origin_body_and_failed_delete_leave_session_available(self):
        snapshot=self.setup_session();route=f"/v1/sessions/{snapshot['session_id']}"
        self.assertEqual(403,self.request("DELETE",route,headers={"Origin":"https://foreign.invalid"})[0])
        self.assertEqual(422,self.request("DELETE",route,json_body={})[0])
        with patch.object(self.runtime._store,"delete_session",side_effect=RuntimeError("disk failure")):
            status,result=self.request("DELETE",route)
            self.assertEqual(503,status);self.assertEqual("session_delete_failed",result["error"]["code"])
        self.assertEqual(200,self.request("GET",route)[0])
        self.assertEqual(200,self.request("DELETE",route)[0])
