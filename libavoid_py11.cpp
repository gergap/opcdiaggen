// SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
// SPDX-License-Identifier: GPL-3.0-only
//
// Minimal pybind11 adapter for the LGPL libavoid router.

#include <cstddef>
#include <algorithm>
#include <stdexcept>
#include <utility>
#include <vector>

#include <pybind11/stl.h>
#include <pybind11/pybind11.h>

#include <libavoid/libavoid.h>

namespace py = pybind11;
using Avoid::ConnDirFlags;

namespace {

struct RectangleInput {
    double x;
    double y;
    double width;
    double height;

    RectangleInput(double x_value, double y_value, double width_value,
                   double height_value)
        : x(x_value), y(y_value), width(width_value), height(height_value) {}
};

struct ConnectionInput {
    std::size_t source_shape;
    std::size_t target_shape;
    double source_x;
    double source_y;
    double target_x;
    double target_y;
    ConnDirFlags source_directions;
    ConnDirFlags target_directions;

    ConnectionInput(std::size_t source_shape_value,
                    std::size_t target_shape_value,
                    double source_x_value, double source_y_value,
                    double target_x_value, double target_y_value,
                    ConnDirFlags source_directions_value,
                    ConnDirFlags target_directions_value)
        : source_shape(source_shape_value), target_shape(target_shape_value),
          source_x(source_x_value), source_y(source_y_value),
          target_x(target_x_value), target_y(target_y_value),
          source_directions(source_directions_value),
          target_directions(target_directions_value) {}
};

bool segment_intersects_rectangle(double x1, double y1, double x2, double y2,
                                  const RectangleInput& rectangle,
                                  double buffer)
{
    const double left = rectangle.x - buffer;
    const double right = rectangle.x + rectangle.width + buffer;
    const double top = rectangle.y - buffer;
    const double bottom = rectangle.y + rectangle.height + buffer;
    if (x1 == x2) {
        return x1 > left && x1 < right &&
               std::max(std::min(y1, y2), top) <
                   std::min(std::max(y1, y2), bottom);
    }
    if (y1 == y2) {
        return y1 > top && y1 < bottom &&
               std::max(std::min(x1, x2), left) <
                   std::min(std::max(x1, x2), right);
    }
    return true;
}

std::vector<std::vector<std::pair<double, double>>> route(
        const std::vector<RectangleInput>& rectangles,
        const std::vector<ConnectionInput>& connections,
        const std::vector<std::vector<std::pair<double, double>>>& fixed_paths,
        double shape_buffer_distance,
        double ideal_nudging_distance,
        double segment_penalty,
        double crossing_penalty)
{
    Avoid::Router router(Avoid::OrthogonalRouting);
    router.setRoutingParameter(Avoid::shapeBufferDistance,
                               shape_buffer_distance);
    router.setRoutingParameter(Avoid::idealNudgingDistance,
                               ideal_nudging_distance);
    router.setRoutingParameter(Avoid::segmentPenalty, segment_penalty);
    router.setRoutingParameter(Avoid::crossingPenalty, crossing_penalty);
    router.setRoutingParameter(Avoid::fixedSharedPathPenalty, crossing_penalty);
    // Keep the endpoint pin positions fixed. Enabling this option can nudge a
    // connector away from its selected anchor and add an unnecessary bend.
    router.setRoutingOption(
        Avoid::nudgeOrthogonalSegmentsConnectedToShapes, false);
    router.setRoutingOption(
        Avoid::penaliseOrthogonalSharedPathsAtConnEnds, true);

    std::vector<Avoid::ShapeRef*> shapes;
    shapes.reserve(rectangles.size());
    for (std::size_t index = 0; index < rectangles.size(); ++index) {
        const auto& rectangle = rectangles[index];
        Avoid::Rectangle polygon(
            Avoid::Point(rectangle.x, rectangle.y),
            Avoid::Point(rectangle.x + rectangle.width,
                         rectangle.y + rectangle.height));
        shapes.push_back(new Avoid::ShapeRef(
            &router, polygon, static_cast<unsigned int>(index + 1)));
    }

    // Fixed hierarchy segments are also narrow buffered obstacles. Libavoid's
    // fixed connector penalties discourage sharing, but do not always prevent
    // a new connector from reusing a fixed segment.
    unsigned int next_id = static_cast<unsigned int>(rectangles.size() + 1);
    for (const auto& fixed_path : fixed_paths) {
        for (std::size_t index = 1; index < fixed_path.size(); ++index) {
            const auto& first = fixed_path[index - 1];
            const auto& second = fixed_path[index];
            const double half_width = 0.5;
            Avoid::Polygon polygon(4);
            if (first.second == second.second) {
                const double left = std::min(first.first, second.first);
                const double right = std::max(first.first, second.first);
                polygon.ps[0] = Avoid::Point(left, first.second - half_width);
                polygon.ps[1] = Avoid::Point(right, first.second - half_width);
                polygon.ps[2] = Avoid::Point(right, first.second + half_width);
                polygon.ps[3] = Avoid::Point(left, first.second + half_width);
            } else {
                const double top = std::min(first.second, second.second);
                const double bottom = std::max(first.second, second.second);
                polygon.ps[0] = Avoid::Point(first.first - half_width, top);
                polygon.ps[1] = Avoid::Point(first.first + half_width, top);
                polygon.ps[2] = Avoid::Point(first.first + half_width, bottom);
                polygon.ps[3] = Avoid::Point(first.first - half_width, bottom);
            }
            shapes.push_back(new Avoid::ShapeRef(&router, polygon, next_id++));
        }
    }

    std::vector<Avoid::ConnRef*> fixed_connectors;
    fixed_connectors.reserve(fixed_paths.size());
    for (std::size_t index = 0; index < fixed_paths.size(); ++index) {
        const auto& fixed_path = fixed_paths[index];
        if (fixed_path.size() < 2) {
            continue;
        }
        Avoid::Polygon route(static_cast<int>(fixed_path.size()));
        for (std::size_t point_index = 0; point_index < fixed_path.size(); ++point_index) {
            route.ps[point_index] = Avoid::Point(
                fixed_path[point_index].first, fixed_path[point_index].second);
        }
        auto* connector = new Avoid::ConnRef(
            &router, next_id++);
        connector->setRoutingType(Avoid::ConnType_Orthogonal);
        connector->setFixedRoute(route);
        fixed_connectors.push_back(connector);
    }

    std::vector<Avoid::ConnRef*> connectors;
    connectors.reserve(connections.size());
    for (std::size_t index = 0; index < connections.size(); ++index) {
        const auto& connection = connections[index];
        if (connection.source_shape >= shapes.size() ||
            connection.target_shape >= shapes.size()) {
            throw std::out_of_range("connection shape index is out of range");
        }
        const unsigned int source_pin_id =
            static_cast<unsigned int>(index * 2 + 1);
        const unsigned int target_pin_id = source_pin_id + 1;
        const auto& source_rectangle = rectangles[connection.source_shape];
        const auto& target_rectangle = rectangles[connection.target_shape];
        const double source_x =
            (connection.source_x - source_rectangle.x) / source_rectangle.width;
        const double source_y =
            (connection.source_y - source_rectangle.y) / source_rectangle.height;
        const double target_x =
            (connection.target_x - target_rectangle.x) / target_rectangle.width;
        const double target_y =
            (connection.target_y - target_rectangle.y) / target_rectangle.height;
        new Avoid::ShapeConnectionPin(
            shapes[connection.source_shape], source_pin_id,
            source_x, source_y, true, shape_buffer_distance,
            connection.source_directions);
        new Avoid::ShapeConnectionPin(
            shapes[connection.target_shape], target_pin_id,
            target_x, target_y, true, shape_buffer_distance,
            connection.target_directions);
        Avoid::ConnEnd source(shapes[connection.source_shape], source_pin_id);
        Avoid::ConnEnd target(shapes[connection.target_shape], target_pin_id);
        auto* connector = new Avoid::ConnRef(
            &router, source, target,
            next_id++);
        connector->setRoutingType(Avoid::ConnType_Orthogonal);
        connector->setHateCrossings(true);
        connectors.push_back(connector);
    }

    router.processTransaction();

    std::vector<std::vector<std::pair<double, double>>> result;
    result.reserve(connectors.size());
    for (std::size_t connection_index = 0;
         connection_index < connectors.size(); ++connection_index) {
        auto* connector = connectors[connection_index];
        const auto& points = connector->displayRoute().ps;
        if (points.size() < 2) {
            throw std::runtime_error("libavoid returned an empty route");
        }
        std::vector<std::pair<double, double>> path;
        path.reserve(points.size());
        for (const auto& point : points) {
            path.emplace_back(point.x, point.y);
        }
        const auto& connection = connections[connection_index];
        for (std::size_t point_index = 1; point_index < path.size(); ++point_index) {
            for (std::size_t shape_index = 0;
                 shape_index < rectangles.size(); ++shape_index) {
                if (shape_index == connection.source_shape && point_index == 1) {
                    continue;
                }
                if (shape_index == connection.target_shape &&
                    point_index == path.size() - 1) {
                    continue;
                }
                if (segment_intersects_rectangle(
                        path[point_index - 1].first,
                        path[point_index - 1].second,
                        path[point_index].first,
                        path[point_index].second,
                        rectangles[shape_index], shape_buffer_distance)) {
                    throw std::runtime_error(
                        "libavoid returned a route through a node");
                }
            }
        }
        result.push_back(std::move(path));
    }
    return result;
}

} // namespace

PYBIND11_MODULE(_libavoid_py11, module)
{
    module.doc() = "Minimal pybind11 binding for libavoid batch routing";
    py::class_<RectangleInput>(module, "Rectangle")
        .def(py::init<double, double, double, double>(),
             py::arg("x"), py::arg("y"), py::arg("width"), py::arg("height"));
    py::class_<ConnectionInput>(module, "Connection")
        .def(py::init<std::size_t, std::size_t, double, double, double, double,
                      ConnDirFlags, ConnDirFlags>(),
             py::arg("source_shape"), py::arg("target_shape"),
             py::arg("source_x"), py::arg("source_y"),
             py::arg("target_x"), py::arg("target_y"),
             py::arg("source_directions"), py::arg("target_directions"));
    module.def("route", &route,
               py::arg("rectangles"), py::arg("connections"),
               py::arg("fixed_paths") = std::vector<std::vector<std::pair<double, double>>>(),
               py::arg("shape_buffer_distance") = 20.0,
               py::arg("ideal_nudging_distance") = 20.0,
               py::arg("segment_penalty") = 10.0,
               py::arg("crossing_penalty") = 1000.0);
    py::setattr(module, "CONN_DIR_UP",
                py::int_(static_cast<unsigned int>(Avoid::ConnDirUp)));
    py::setattr(module, "CONN_DIR_DOWN",
                py::int_(static_cast<unsigned int>(Avoid::ConnDirDown)));
    py::setattr(module, "CONN_DIR_LEFT",
                py::int_(static_cast<unsigned int>(Avoid::ConnDirLeft)));
    py::setattr(module, "CONN_DIR_RIGHT",
                py::int_(static_cast<unsigned int>(Avoid::ConnDirRight)));
}
