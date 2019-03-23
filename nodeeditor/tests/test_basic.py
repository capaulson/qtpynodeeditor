import pytest
import qtpy.QtCore

import nodeeditor
from nodeeditor import PortType


class MyNodeData(nodeeditor.NodeData):
    data_type = nodeeditor.NodeDataType('MyNodeData', 'My Node Data')


class BasicDataModel(nodeeditor.NodeDataModel):
    name = 'MyDataModel'
    caption = 'Caption'
    caption_visible = True
    num_ports = {'input': 3,
                 'output': 3
                 }

    def model(self):
        return 'MyDataModel'

    def data_type(self, port_type, port_index):
        return MyNodeData.data_type

    def out_data(self, data):
        return MyNodeData()

    def set_in_data(self, node_data, port):
        ...

    def embedded_widget(self):
        return None


# @pytest.mark.parametrize("model_class", [...])
@pytest.fixture(scope='function')
def model():
    return BasicDataModel


@pytest.fixture(scope='function')
def registry(model):
    registry = nodeeditor.DataModelRegistry()
    registry.register_model(model, category='My Category')
    return registry


@pytest.fixture(scope='function')
def scene(qapp, registry):
    return nodeeditor.FlowScene(registry=registry)


@pytest.fixture(scope='function')
def view(qtbot, scene):
    view = nodeeditor.FlowView(scene)
    qtbot.addWidget(view)
    view.setWindowTitle("nodeeditor test suite")
    view.resize(800, 600)
    view.show()
    return view


def test_instantiation(view):
    ...


def test_create_node(scene, model):
    node = scene.create_node(model)
    assert node in scene.nodes().values()
    assert node.id in scene.nodes()


def test_selected_nodes(scene, model):
    node = scene.create_node(model)
    node.graphics_object.setSelected(True)
    assert scene.selected_nodes() == [node]


def test_create_connection(scene, view, model):
    node1 = scene.create_node(model)
    node2 = scene.create_node(model)
    scene.create_connection(
        node_in=node1, port_index_in=1,
        node_out=node2, port_index_out=2,
        converter=None
    )

    view.update()

    assert len(scene.connections()) == 1
    all_c1 = node1.state.all_connections
    assert len(all_c1) == 1
    all_c2 = node1.state.all_connections
    assert len(all_c2) == 1
    assert all_c1 == all_c2

    conn, = all_c1
    # conn_state = conn.state
    in_node = conn.get_node(PortType.input)
    in_port = conn.get_port_index(PortType.input)
    out_node = conn.get_node(PortType.output)
    out_port = conn.get_port_index(PortType.output)
    assert in_node == node1
    assert in_port == 1
    assert out_node == node2
    assert out_port == 2

    scene.delete_connection(conn)
    assert len(scene.connections()) == 0
    all_c1 = node1.state.all_connections
    assert len(all_c1) == 0
    all_c2 = node1.state.all_connections
    assert len(all_c2) == 0


def test_clear_scene(scene, view, model):
    node1 = scene.create_node(model)
    node2 = scene.create_node(model)
    scene.create_connection(
        node_in=node1, port_index_in=1,
        node_out=node2, port_index_out=2,
        converter=None
    )

    scene.clear_scene()

    assert len(scene.nodes()) == 0
    assert len(scene.connections()) == 0
    all_c1 = node1.state.all_connections
    assert len(all_c1) == 0
    all_c2 = node1.state.all_connections
    assert len(all_c2) == 0


def test_save_load(tmp_path, scene, view, model):
    node1 = scene.create_node(model)
    node2 = scene.create_node(model)

    created_nodes = (node1, node2)

    assert len(scene.nodes()) == len(created_nodes)

    for node in created_nodes:
        assert node in scene.nodes().values()
        assert node.id in scene.nodes()

    fname = tmp_path / 'temp.flow'
    scene.save(fname)
    scene.load(fname)

    assert len(scene.nodes()) == len(created_nodes)

    for node in created_nodes:
        assert node not in scene.nodes().values()
        assert node.id in scene.nodes()


@pytest.mark.parametrize('reset, port_type',
                         [(True, 'input'),
                          (False, 'output')])
def test_smoke_reacting(scene, view, model, reset, port_type):
    node = scene.create_node(model)
    dtype = node.data.data_type(port_type, 0)
    node.react_to_possible_connection(
        reacting_port_type=port_type,
        reacting_data_type=dtype,
        scene_point=qtpy.QtCore.QPointF(0, 0),
    )
    view.update()
    if reset:
        node.reset_reaction_to_connection()


def test_smoke_node_size_updated(scene, view, model):
    node = scene.create_node(model)
    node.on_node_size_updated()
    view.update()


def test_smoke_connection_interaction(scene, view, model):
    node1 = scene.create_node(model)
    node2 = scene.create_node(model)
    conn = scene.create_connection_node(node1, PortType.output, port_index=0)
    interaction = nodeeditor.NodeConnectionInteraction(
        node=node2, connection=conn, scene=scene)

    node_scene_transform = node2.graphics_object.sceneTransform()
    pos = node2.geometry.port_scene_position(PortType.input, 0,
                                             node_scene_transform)

    conn.geometry.set_end_point(PortType.input, pos)

    with pytest.raises(nodeeditor.ConnectionPointFailure):
        interaction.can_connect()

    conn.geometry.set_end_point(PortType.output, pos)
    with pytest.raises(nodeeditor.ConnectionPointFailure):
        interaction.can_connect()

    assert interaction.node_port_is_empty(PortType.input, 0)
    assert interaction.connection_required_port == PortType.input

    # TODO node still not on it?
    interaction.can_connect = lambda: (0, None)

    assert interaction.try_connect()

    interaction.disconnect(PortType.output)
    interaction.connection_end_scene_position(PortType.input)
    interaction.node_port_scene_position(PortType.input, 0)
    interaction.node_port_index_under_scene_point(PortType.input, qtpy.QtCore.QPointF(0, 0))
