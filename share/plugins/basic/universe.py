# Zeobuilder is an extensible GUI-toolkit for molecular model construction.
# Copyright (C) 2005 Toon Verstraelen
#
# This file is part of Zeobuilder.
#
# Zeobuilder is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# --


from zeobuilder import context
from zeobuilder.actions.composed import ImmediateWithMemory, Immediate, UserError, Parameters
from zeobuilder.actions.collections.menu import MenuInfo
from zeobuilder.nodes.meta import NodeClass, Property
from zeobuilder.nodes.elementary import GLContainerBase, GLReferentBase
from zeobuilder.nodes.model_object import ModelObjectInfo
from zeobuilder.nodes.parent_mixin import ReferentMixin
from zeobuilder.nodes.glmixin import GLTransformationMixin
from zeobuilder.nodes.helpers import FrameAxes
from zeobuilder.nodes.reference import SpatialReference
from zeobuilder.nodes.vector import Vector
from zeobuilder.gui.fields_dialogs import FieldsDialogSimple, DialogFieldInfo
from zeobuilder.zml import dump_to_file, load_from_file
import zeobuilder.actions.primitive as primitive
import zeobuilder.gui.fields as fields
import zeobuilder.authors as authors

from molmod.transformations import Translation

from molmod.unit_cell import UnitCell
from molmod.units import angstrom

from OpenGL.GL import *
import numpy, gtk

import math, copy, StringIO


class GLPeriodicContainer(GLContainerBase, UnitCell):


    __metaclass__ = NodeClass

    #
    # State
    #

    def initstate(self, **initstate):
        GLContainerBase.initstate(self, **initstate)
        self.child_connections = {}
        for child in self.children:
            if isinstance(child, GLTransformationMixin):
                self.child_connections[child] = child.connect("on-transformation-list-invalidated", self.on_child_transformation_changed)

    #
    # Properties
    #

    def update_vectors(self):
        for node in self.children:
            if isinstance(node, GLReferentBase):
                node.invalidate_draw_list()
                node.invalidate_boundingbox_list()

    def set_cell(self, cell):
        UnitCell.set_cell(self, cell)
        self.update_child_positions()
        self.invalidate_boundingbox_list()
        self.invalidate_draw_list()
        self.update_vectors()

    def set_cell_active(self, cell_active):
        UnitCell.set_cell_active(self, cell_active)
        self.update_child_positions()
        self.invalidate_draw_list()
        self.invalidate_boundingbox_list()
        self.update_vectors()

    #
    # Properties
    #

    properties = [
        # The columns of the cell are the vectors that correspond
        # to the ridges of the parallellepipedum that describe the unit cell. In
        # other words this matrix transforms a unit cube to the unit cell.
        Property("cell", numpy.array([[10, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]])*angstrom, lambda self: self.cell, set_cell),
        Property("cell_active", numpy.array([False, False, False]), lambda self: self.cell_active, set_cell_active),
    ]

    #
    # Dialog fields (see action EditProperties)
    #

    dialog_fields = set([
        DialogFieldInfo("Unit cell", (5, 0), fields.composed.CellMatrix(
            label_text="Cell dimensions",
            attribute_name="cell",
        )),
        DialogFieldInfo("Unit cell", (5, 1), fields.composed.CellActive(
            label_text="Active directions",
            attribute_name="cell_active",
        )),
    ])

    #
    # Tree
    #

    def add(self, modelobject, index=-1):
        GLContainerBase.add(self, modelobject, index)
        if isinstance(modelobject, GLTransformationMixin):
            #print "ADD to universe", modelobject.name
            self.child_connections[modelobject] = modelobject.connect("on-transformation-list-invalidated", self.on_child_transformation_changed)
            self.on_child_transformation_changed(modelobject)

    def add_many(self, modelobjects, index=-1):
        GLContainerBase.add_many(self, modelobjects, index)
        for modelobject in modelobjects:
            if isinstance(modelobject, GLTransformationMixin):
                #print "ADD MANY to universe", modelobject.name
                self.child_connections[modelobject] = modelobject.connect("on-transformation-list-invalidated", self.on_child_transformation_changed)
                self.on_child_transformation_changed(modelobject)

    def remove(self, modelobject):
        GLContainerBase.remove(self, modelobject)
        if isinstance(modelobject, GLTransformationMixin):
            #print "REMOVE from universe", modelobject.name
            modelobject.disconnect(self.child_connections[modelobject])

    #
    # Invalidate
    #

    def on_child_transformation_changed(self, child):
        self.wrap(child)

    #
    # Wrapping
    #

    def wrap(self, child):
        cell_index = self.to_index(child.transformation.t)
        if cell_index.any():
            new_transformation = copy.deepcopy(child.transformation)
            new_transformation.t -= numpy.dot(self.cell, cell_index)
            primitive.SetProperty(child, "transformation", new_transformation)

    def update_child_positions(self):
        if not self.cell_active.any(): return
        for child in self.children:
            if isinstance(child, GLTransformationMixin):
                self.wrap(child)

    def shortest_vector(self, delta):
        return UnitCell.shortest_vector(self, delta)


def yield_all_positions(l):
    if len(l) == 0:
        yield []
    else:
        for rest in yield_all_positions(l[1:]):
            for i in xrange(int(l[0])):
                yield [i] + rest


class Universe(GLPeriodicContainer, FrameAxes):
    info = ModelObjectInfo("plugins/basic/universe.svg")
    authors = [authors.toon_verstraelen]
    clip_margin = 0.1

    #
    # State
    #

    def initnonstate(self):
        GLPeriodicContainer.initnonstate(self)
        self.model_center = Translation()

    #
    # Properties
    #

    def set_cell(self, cell):
        GLPeriodicContainer.set_cell(self, cell)
        self.update_clip_planes()
        self.model_center.t = 0.5*numpy.dot(self.cell, self.repetitions * self.cell_active)
        self.invalidate_total_list()
        self.invalidate_box_list()

    def set_cell_active(self, cell_active):
        GLPeriodicContainer.set_cell_active(self, cell_active)
        self.update_clip_planes()
        self.model_center.t = 0.5*numpy.dot(self.cell, self.repetitions * self.cell_active)
        self.invalidate_total_list()
        self.invalidate_box_list()

    def set_repetitions(self, repetitions):
        self.repetitions = repetitions
        self.update_clip_planes()
        self.model_center.t = 0.5*numpy.dot(self.cell, self.repetitions * self.cell_active)
        self.invalidate_box_list()
        self.invalidate_total_list()

    def set_box_visible(self, box_visible):
        self.box_visible = box_visible
        self.invalidate_total_list()

    def set_clipping(self, clipping):
        self.clipping = clipping
        self.invalidate_total_list()
        self.invalidate_box_list()
        self.update_clip_planes()

    properties = [
        Property("repetitions", numpy.array([1, 1, 1], int), lambda self: self.repetitions, set_repetitions),
        Property("box_visible", True, lambda self: self.box_visible, set_box_visible),
        Property("clipping", False, lambda self: self.clipping, set_clipping),
    ]

    #
    # Dialog fields (see action EditProperties)
    #

    dialog_fields = set([
        DialogFieldInfo("Unit cell", (5, 2), fields.composed.Repetitions(
            label_text="Repetitions",
            attribute_name="repetitions",
        )),
        DialogFieldInfo("Markup", (1, 5),fields.edit.CheckButton(
            label_text="Show periodic box (if active)",
            attribute_name="box_visible",
        )),
        DialogFieldInfo("Markup", (1, 6),fields.edit.CheckButton(
            label_text="Clip the unit cell contents.",
            attribute_name="clipping",
        )),
    ])

    #
    # Tree
    #

    @classmethod
    def check_add(Class, ModelObjectClass):
        if not GLPeriodicContainer.check_add(ModelObjectClass): return False
        if issubclass(ModelObjectClass, Universe): return False
        return True

    #
    # OpenGL
    #

    def initialize_gl(self):
        self.set_clip_planes()
        self.box_list = glGenLists(1)
        ##print "Created box list (%i): %s" % (self.box_list, self.get_name())
        self.box_list_valid = True
        GLPeriodicContainer.initialize_gl(self)

    def cleanup_gl(self):
        GLPeriodicContainer.cleanup_gl(self)
        ##print "Deleting box list (%i): %s" % (self.box_list, self.get_name())
        glDeleteLists(self.box_list, 1)
        del self.box_list
        del self.box_list_valid
        self.unset_clip_planes()

    #
    # Clipping
    #

    def update_clip_planes(self):
        if self.gl_active > 0:
            self.unset_clip_planes()
            self.set_clip_planes()

    def set_clip_planes(self):
        if not self.clipping:
            return
        scene = context.application.main.drawing_area.scene
        assert len(scene.clip_planes) == 0
        active, inactive = self.get_active_inactive()
        planes = [
            (GL_CLIP_PLANE0, GL_CLIP_PLANE1),
            (GL_CLIP_PLANE2, GL_CLIP_PLANE3),
            (GL_CLIP_PLANE4, GL_CLIP_PLANE5),
        ]
        for index, (PLANE_A, PLANE_B) in zip(active, planes):
            axis = self.cell[:,index]
            ortho = self.cell_reciproke[index] / numpy.linalg.norm(self.cell_reciproke[index])
            length = abs(numpy.dot(ortho, axis))
            repetitions = self.repetitions[index]
            scene.clip_planes[PLANE_A] = numpy.array(list( ortho) + [self.clip_margin])
            scene.clip_planes[PLANE_B] = numpy.array(list(-ortho) + [repetitions*length + self.clip_margin])

    def unset_clip_planes(self):
        context.application.main.drawing_area.scene.clip_planes = {}
        context.application.main.drawing_area.queue_draw()

    #
    # Invalidation
    #


    def invalidate_box_list(self):
        if self.gl_active > 0 and self.box_list_valid:
            self.box_list_valid = False
            context.application.main.drawing_area.queue_draw()
            context.application.main.drawing_area.scene.add_revalidation(self.revalidate_box_list)
            ##print "EMIT %s: on-box-list-invalidated" % self.get_name()

    def invalidate_all_lists(self):
        self.invalidate_box_list()
        GLPeriodicContainer.invalidate_all_lists(self)

    #
    # Draw
    #

    def draw_box_helper(self, light, draw_line, set_color):
        col  = {True: 4.0, False: 2.5}[light]
        sat  = {True: 0.0, False: 0.5}[light]
        gray = {True: 4.0, False: 2.5}[light]

        def draw_three(origin):
            if self.cell_active[0]:
                set_color(col, sat, sat)
                draw_line(origin, origin+self.cell[:,0])
            if self.cell_active[1]:
                set_color(sat, col, sat)
                draw_line(origin, origin+self.cell[:,1])
            if self.cell_active[2]:
                set_color(sat, sat, col)
                draw_line(origin, origin+self.cell[:,2])

        def draw_gray(origin, axis1, axis2, n1, n2, delta, nd):
            set_color(gray, gray, gray)
            if n1 == 0 and n2 == 0:
                return
            for i1 in xrange(n1+1):
                if i1 == 0:
                    b2 = 1
                    draw_line(origin+delta, origin+nd*delta)
                else:
                    b2 = 0
                for i2 in xrange(b2, n2+1):
                    draw_line(origin+i1*axis1+i2*axis2, origin+i1*axis1+i2*axis2+nd*delta)

        def draw_ortho(origin, axis1, axis2, n1, n2, delta):
            set_color(gray, gray, gray)
            if n1 == 0 and n2 == 0:
                return
            for i1 in xrange(n1+1):
                for i2 in xrange(n2+1):
                    draw_line(
                        origin + i1*axis1 + i2*axis2 - 0.5*delta,
                        origin + i1*axis1 + i2*axis2 + 0.5*delta
                    )

        origin = numpy.zeros(3, float)
        draw_three(origin)
        repetitions = self.repetitions*self.cell_active

        if self.cell_active[2]:
            draw_gray(origin, self.cell[:,0], self.cell[:,1], repetitions[0], repetitions[1], self.cell[:,2], repetitions[2])
        else:
            draw_ortho(origin, self.cell[:,0], self.cell[:,1], repetitions[0], repetitions[1], self.cell[:,2])

        if self.cell_active[0]:
            draw_gray(origin, self.cell[:,1], self.cell[:,2], repetitions[1], repetitions[2], self.cell[:,0], repetitions[0])
        else:
            draw_ortho(origin, self.cell[:,1], self.cell[:,2], repetitions[1], repetitions[2], self.cell[:,0])

        if self.cell_active[1]:
            draw_gray(origin, self.cell[:,2], self.cell[:,0], repetitions[2], repetitions[0], self.cell[:,1], repetitions[1])
        else:
            draw_ortho(origin, self.cell[:,2], self.cell[:,0], repetitions[2], repetitions[0], self.cell[:,1])

    def draw_box(self):
        def draw_line(begin, end):
            glVertexf(begin)
            glVertexf(end)

        def set_color(r, g, b):
            glMaterial(GL_FRONT, GL_AMBIENT, [r, g, b, 1.0])

        glLineWidth(2)
        glMaterial(GL_FRONT, GL_DIFFUSE, [0.0, 0.0, 0.0, 0.0])
        glMaterial(GL_FRONT, GL_SPECULAR, [0.0, 0.0, 0.0, 0.0])
        glBegin(GL_LINES)
        self.draw_box_helper(self.selected, draw_line, set_color)
        glEnd()
        glMaterial(GL_FRONT, GL_SPECULAR, [0.7, 0.7, 0.7, 1.0])

    def draw(self):
        FrameAxes.draw(self, self.selected)
        GLPeriodicContainer.draw(self)

    def write_pov(self, indenter):
        indenter.write_line("union {", 1)
        FrameAxes.write_pov(self, indenter)
        if self.box_visible and sum(self.cell_active) > 0:
            color = numpy.zeros(3, float)
            def draw_line(begin, end):
                indenter.write_line("cylinder {", 1)
                indenter.write_line("<%f, %f, %f>, <%f, %f, %f>, 0.05" % (tuple(begin) + tuple(end)))
                indenter.write_line("pigment { rgb <%f, %f, %f> }" % tuple(color))
                indenter.write_line("}", -1)

            def set_color(r, g, b):
                color[0] = r
                color[1] = g
                color[2] = b

            self.draw_box_helper(True, draw_line, set_color)
        indenter.write_line("}", -1)

    #
    # Revalidation
    #

    def revalidate_box_list(self):
        if self.gl_active > 0:
            ##print "Compiling box list (%i): %s" % (self.box_list,  self.get_name())
            glNewList(self.box_list, GL_COMPILE)
            glPushMatrix()
            if sum(self.cell_active) > 0:
                self.draw_box()
            glEndList()
            self.box_list_valid = True

    def revalidate_total_list(self):
        if self.gl_active > 0:
            ##print "Compiling total list (%i): %s" % (self.total_list, self.get_name())
            glNewList(self.total_list, GL_COMPILE)
            if self.visible:
                glPushName(self.draw_list)
                if self.box_visible: glCallList(self.box_list)
                if self.selected and sum(self.cell_active) == 0:
                    glCallList(self.boundingbox_list)

                # repeat the draw list for all the unit cell images.
                if self.clipping:
                    repetitions = (self.repetitions + 2) * self.cell_active + 1 - self.cell_active
                else:
                    repetitions = self.repetitions * self.cell_active + 1 - self.cell_active
                for position in yield_all_positions(repetitions):
                    glPushMatrix()
                    t = numpy.dot(self.cell, numpy.array(position) - self.cell_active * self.clipping)
                    glTranslate(t[0], t[1], t[2])
                    glCallList(self.draw_list)
                    glPopMatrix()

                glPopMatrix()
                glPopName()
            glEndList()
            self.total_list_valid = True

    def revalidate_bounding_box(self):
        GLPeriodicContainer.revalidate_bounding_box(self)
        FrameAxes.extend_bounding_box(self, self.bounding_box)

    #
    # Signal handlers
    #

    def on_select_chaged(self, selected):
        GLPeriodicContainer.on_select_chaged(self, selected)
        self.invalidate_box_list()


class UnitCellToCluster(ImmediateWithMemory):
    description = "Convert the unit cell to a cluster"
    menu_info = MenuInfo("default/_Object:tools/_Unit Cell:default", "_To cluster", order=(0, 4, 1, 4, 0, 0))
    authors = [authors.toon_verstraelen]
    store_last_parameters = False

    parameters_dialog = FieldsDialogSimple(
        "Unit cell to cluster",
        fields.group.Table(
            fields=[
                fields.optional.CheckOptional(
                    fields.composed.ComposedArray(
                        FieldClass=fields.faulty.Float,
                        array_name=(ridge+".%s"),
                        suffices=["min", "max"],
                        attribute_name="interval_%s" % ridge.lower(),
                        one_row=True,
                        short=False,
                    )
                )
                for ridge in ["A", "B", "C"]
            ],
            label_text="The cutoff region in fractional coordinates:"
        ),
        ((gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL), (gtk.STOCK_OK, gtk.RESPONSE_OK))
    )

    @staticmethod
    def analyze_selection(parameters=None):
        # A) calling ancestor
        if not ImmediateWithMemory.analyze_selection(parameters): return False
        # B) validating
        universe = context.application.model.universe
        if sum(universe.cell_active) == 0: return False
        if hasattr(parameters, "interval_a") and not universe.cell_active[0]: return False
        if hasattr(parameters, "interval_b") and not universe.cell_active[1]: return False
        if hasattr(parameters, "interval_c") and not universe.cell_active[2]: return False
        # C) passed all tests:
        return True

    @classmethod
    def default_parameters(cls):
        result = Parameters()
        universe = context.application.model.universe
        if universe.cell_active[0]:
            result.interval_a = numpy.array([0.0, universe.repetitions[0]], float)
        if universe.cell_active[1]:
            result.interval_b = numpy.array([0.0, universe.repetitions[1]], float)
        if universe.cell_active[2]:
            result.interval_c = numpy.array([0.0, universe.repetitions[2]], float)
        return result

    def do(self):
        universe = context.application.model.universe
        def extend_to_cluster(axis, interval):
            if interval is None: return
            assert universe.cell_active[axis]
            interval.sort()
            index_min = int(math.floor(interval[0]))
            index_max = int(math.ceil(interval[1]))

            positioned = [
                node
                for node
                in universe.children
                if (
                    isinstance(node, GLTransformationMixin) and
                    isinstance(node.transformation, Translation)
                )
            ]
            if len(positioned) == 0: return

            serialized = StringIO.StringIO()
            dump_to_file(serialized, positioned)

            # replication the positioned objects
            new_children = {}
            for cell_index in xrange(index_min, index_max+1):
                serialized.seek(0)
                nodes = load_from_file(serialized)
                new_children[cell_index] = {}
                for node_index, node in enumerate(nodes):
                    position = node.transformation.t + universe.cell[:,axis]*cell_index
                    fractional = universe.to_fractional(position)
                    if (fractional[axis] < interval[0]) or (fractional[axis] > interval[1]):
                        continue
                    node.transformation.t = position
                    new_children[cell_index][node_index] = node

            new_connectors = []
            # replicate the objects that connect these positioned objects
            for cell_index in xrange(index_min, index_max+1):
                for connector in universe.children:
                    if not isinstance(connector, ReferentMixin): continue
                    skip = False
                    for reference in connector.children:
                        if not isinstance(reference, SpatialReference):
                            skip = True
                            break
                    if skip: continue

                    first_target_orig = connector.children[0].target
                    first_target_index = positioned.index(first_target_orig)
                    first_target = new_children[cell_index].get(first_target_index)
                    if first_target is None:
                        continue
                    new_targets = [first_target]

                    skip = False
                    for reference in connector.children[1:]:
                        other_target_orig = reference.target
                        shortest_vector = universe.shortest_vector((
                            other_target_orig.transformation.t
                           -first_target_orig.transformation.t
                        ))
                        translation = first_target.transformation.t + shortest_vector
                        other_cell_index = universe.to_index(translation)
                        other_target_index = positioned.index(other_target_orig)
                        other_cell_children = new_children.get(other_cell_index[axis])
                        if other_cell_children is None:
                            skip = True
                            break
                        other_target = other_cell_children.get(other_target_index)
                        if other_target is None:
                            skip = True
                            break
                        new_targets.append(other_target)
                    if skip:
                        del new_targets
                        continue

                    state = connector.__getstate__()
                    state["targets"] = new_targets
                    new_connectors.append(connector.__class__(**state))

            # forget about the others

            serialized.close()
            del serialized

            # remove the existing nodes

            while len(universe.children) > 0:
                primitive.Delete(universe.children[0])
            del positioned

            # remove the periodicity

            tmp_active = universe.cell_active.copy()
            tmp_active[axis] = False
            primitive.SetProperty(universe, "cell_active", tmp_active)

            # add the new nodes

            for nodes in new_children.itervalues():
                for node in nodes.itervalues():
                    primitive.Add(node, universe)

            for connector in new_connectors:
                primitive.Add(connector, universe)


        if hasattr(self.parameters, "interval_a"):
            extend_to_cluster(0, self.parameters.interval_a)
        if hasattr(self.parameters, "interval_b"):
            extend_to_cluster(1, self.parameters.interval_b)
        if hasattr(self.parameters, "interval_c"):
            extend_to_cluster(2, self.parameters.interval_c)


class SuperCell(ImmediateWithMemory):
    description = "Convert the unit cell to larger unit cell"
    menu_info = MenuInfo("default/_Object:tools/_Unit Cell:default", "_Super cell", order=(0, 4, 1, 4, 0, 1))
    authors = [authors.toon_verstraelen]
    store_last_parameters = False

    parameters_dialog = FieldsDialogSimple(
        "Super cell",
        fields.group.Table(
            fields=[
                fields.faulty.Int(
                    attribute_name="repetitions_%s" % ridge.lower(),
                    label_text=ridge,
                    minimum=1,
                )
                for ridge in ["A", "B", "C"]
            ],
            label_text="The number of repetitions along each active axis."
        ),
        ((gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL), (gtk.STOCK_OK, gtk.RESPONSE_OK))
    )

    @staticmethod
    def analyze_selection(parameters=None):
        # A) calling ancestor
        if not ImmediateWithMemory.analyze_selection(parameters): return False
        # B) validating
        universe = context.application.model.universe
        if sum(universe.cell_active) == 0: return False
        if hasattr(parameters, "repetitions_a") and not universe.cell_active[0]: return False
        if hasattr(parameters, "repetitions_b") and not universe.cell_active[1]: return False
        if hasattr(parameters, "repetitions_c") and not universe.cell_active[2]: return False
        # C) passed all tests:
        return True

    @classmethod
    def default_parameters(cls):
        result = Parameters()
        universe = context.application.model.universe
        if universe.cell_active[0]:
            result.repetitions_a = universe.repetitions[0]
        if universe.cell_active[1]:
            result.repetitions_b = universe.repetitions[1]
        if universe.cell_active[2]:
            result.repetitions_c = universe.repetitions[2]
        return result

    def do(self):
        # create the repetitions vector
        repetitions = []

        if hasattr(self.parameters, "repetitions_a"):
            repetitions.append(self.parameters.repetitions_a)
        else:
            repetitions.append(1)

        if hasattr(self.parameters, "repetitions_b"):
            repetitions.append(self.parameters.repetitions_b)
        else:
            repetitions.append(1)

        if hasattr(self.parameters, "repetitions_c"):
            repetitions.append(self.parameters.repetitions_c)
        else:
            repetitions.append(1)

        repetitions = numpy.array(repetitions, int)

        # serialize the positioned children

        universe = context.application.model.universe

        positioned = [
            node
            for node
            in universe.children
            if (
                isinstance(node, GLTransformationMixin) and
                isinstance(node.transformation, Translation)
            )
        ]
        if len(positioned) == 0: return

        serialized = StringIO.StringIO()
        dump_to_file(serialized, positioned)

        # create the replica's

        # replication the positioned objects
        new_children = {}
        for cell_index in yield_all_positions(repetitions):
            cell_index = numpy.array(cell_index)
            cell_hash = tuple(cell_index)
            serialized.seek(0)
            nodes = load_from_file(serialized)
            new_children[cell_hash] = nodes
            for node in nodes:
                node.transformation.t += numpy.dot(universe.cell, cell_index - 0.5*(repetitions - 1))

        new_connectors = []
        # replicate the objects that connect these positioned objects
        for cell_index in yield_all_positions(repetitions):
            cell_index = numpy.array(cell_index)
            cell_hash = tuple(cell_index)
            for connector in universe.children:
                if not isinstance(connector, ReferentMixin): continue
                skip = False
                for reference in connector.children:
                    if not isinstance(reference, SpatialReference):
                        skip = True
                        break
                if skip: continue

                first_target_orig = connector.children[0].target
                first_target_index = positioned.index(first_target_orig)
                first_target = new_children[cell_hash][first_target_index]
                assert first_target is not None
                new_targets = [first_target]

                for reference in connector.children[1:]:
                    other_target_orig = reference.target
                    shortest_vector = universe.shortest_vector((
                        other_target_orig.transformation.t
                        -first_target_orig.transformation.t
                    ))
                    translation = first_target.transformation.t + shortest_vector
                    other_cell_index = universe.to_index(translation - numpy.dot(universe.cell, -0.5*(repetitions - 1)))
                    other_cell_index %= repetitions
                    other_cell_hash = tuple(other_cell_index)
                    other_target_index = positioned.index(other_target_orig)
                    other_cell_children = new_children.get(other_cell_hash)
                    assert other_cell_children is not None
                    other_target = other_cell_children[other_target_index]
                    assert other_target is not None
                    new_targets.append(other_target)

                state = connector.__getstate__()
                state["targets"] = new_targets
                new_connectors.append(connector.__class__(**state))

        # forget about the others

        serialized.close()
        del serialized

        # remove the existing nodes

        while len(universe.children) > 0:
            primitive.Delete(universe.children[0])
        del positioned

        # multiply the cell matrix and reset the number of repetitions

        new_matrix = universe.cell * repetitions
        primitive.SetProperty(universe, "cell", new_matrix)
        primitive.SetProperty(universe, "repetitions", numpy.array([1, 1, 1], int))

        # add the new nodes

        for nodes in new_children.itervalues():
            for node in nodes:
                primitive.Add(node, universe)

        for connector in new_connectors:
            primitive.Add(connector, universe)


class DefineUnitCellVectors(Immediate):
    description = "Wraps the universe in a unit cell"
    menu_info = MenuInfo("default/_Object:tools/_Unit Cell:default", "_Define unit cell vector(s)", order=(0, 4, 1, 4, 0, 2))
    repeatable = False
    authors = [authors.toon_verstraelen]

    @staticmethod
    def analyze_selection():
        # A) calling ancestor
        if not Immediate.analyze_selection(): return False
        # B) validating
        cache = context.application.cache
        if len(cache.nodes) < 1: return False
        if len(cache.nodes) + sum(context.application.model.universe.cell_active) > 3: return False
        for Class in cache.classes:
            if not issubclass(Class, Vector): return False
        # C) passed all tests:
        return True

    def do(self):
        vectors = context.application.cache.nodes
        universe = context.application.model.root[0]
        new_unit_cell = UnitCell()
        new_unit_cell.cell_active = copy.deepcopy(universe.cell_active)
        new_unit_cell.cell = copy.deepcopy(universe.cell)
        try:
            for vector in vectors:
                new_unit_cell.add_cell_vector(vector.shortest_vector_relative_to(universe))
        except ValueError:
            if len(vectors) == 1:
                raise UserError("Failed to add the selected vector as cell vector since it would make the unit cell singular.")
            else:
                raise UserError("Failed to add the selected vectors as cell vectors since they would make the unit cell singular.")
        primitive.SetProperty(universe, "cell", new_unit_cell.cell)
        primitive.SetProperty(universe, "cell_active", new_unit_cell.cell_active)



nodes = {
    "Universe": Universe
}

actions = {
    "UnitCellToCluster": UnitCellToCluster,
    "SuperCell": SuperCell,
    "DefineUnitCellVectors": DefineUnitCellVectors,
}