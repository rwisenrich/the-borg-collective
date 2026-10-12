import tempfile
import threading
import unittest
from pathlib import Path
from borg.crypto import create_identity,load_identity
from borg.tensor import DenseLayer,make_layer_server,pipeline,pipeline_redundant


class DistributedNeuralMath(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        p=Path(self.temp.name)
        self.key=p/'operator.key'
        self.outsider=p/'outsider.key'
        create_identity(self.key,'Operator who requested the inference')
        create_identity(self.outsider,'Uninvited client')

    def test_actual_two_networked_neural_layers(self):
        a=DenseLayer([[.1,.3,-.2],[.7,.5,.4],[.1,-.1,.6]],[.3,-.2,.1],'relu')
        b=DenseLayer([[.5,.1,.8],[-.6,.4,.2]],[.05,-.3],'tanh')
        servers=[make_layer_server(layer,[load_identity(self.key)]) for layer in (a,b)]
        threads=[]
        for server in servers:
            t=threading.Thread(target=server.serve_forever,daemon=True)
            t.start();threads.append(t)
        try:
            x=[2.0,-1.0,.75]
            expected=b.forward(a.forward(x))
            endpoints=[f'http://127.0.0.1:{s.server_port}' for s in servers]
            actual=pipeline(endpoints,self.key,x)
            for exp,got in zip(expected,actual):
                self.assertAlmostEqual(exp,got,places=13)
            with self.assertRaises(RuntimeError):
                pipeline(endpoints,self.outsider,x)
        finally:
            for server in servers:server.shutdown();server.server_close()
            for thread in threads:thread.join(timeout=3)

    def test_two_of_three_matching_layers_defeat_bad_output(self):
        layer=DenseLayer([[.2,.6],[.4,-.7]],[.1,.2],'tanh')
        bad=DenseLayer([[.2,.6],[.4,-.7]],[1.1,.2],'tanh')
        servers=[make_layer_server(z,[load_identity(self.key)]) for z in (bad,layer,layer)]
        threads=[]
        for server in servers:
            t=threading.Thread(target=server.serve_forever,daemon=True)
            t.start();threads.append(t)
        try:
            urls=[f'http://127.0.0.1:{s.server_port}' for s in servers]
            actual=pipeline_redundant([urls],self.key,[1.3,.5],verify_replicas=True)
            expected=layer.forward([1.3,.5])
            for e,a in zip(expected,actual):self.assertAlmostEqual(e,a,places=12)
        finally:
            for server in servers:server.shutdown();server.server_close()
            for t in threads:t.join(timeout=3)

    def test_shape_and_numeric_validation(self):
        layer=DenseLayer([[1,2]],[.2])
        for value in ([1], [float('nan'),2], [float('inf'),2], [1,2,3]):
            with self.assertRaises(ValueError):layer.forward(value)
        with self.assertRaises(ValueError):
            DenseLayer([[1,2],[3]],[1,2])

if __name__=='__main__':unittest.main()
