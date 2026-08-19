document.addEventListener("DOMContentLoaded", function () {
  var el = document.getElementById("review-map");
  if (!el || !window.L) {
    return;
  }
  var raw = el.getAttribute("data-points") || "[]";
  var points;
  try {
    points = JSON.parse(raw);
  } catch (err) {
    return;
  }
  if (!points.length) {
    return;
  }
  var map = L.map(el);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
    maxZoom: 19,
  }).addTo(map);
  function textPopup(label) {
    var node = document.createElement("div");
    node.textContent = label || "";
    return node;
  }
  var bounds = [];
  var incoming = null;
  points.forEach(function (point) {
    var lat = Number(point.lat);
    var lon = Number(point.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      return;
    }
    var latlng = [lat, lon];
    bounds.push(latlng);
    var color = point.kind === "incoming" ? "#2a7f4f" : "#c45c12";
    L.circleMarker(latlng, {
      radius: 9,
      color: color,
      fillColor: color,
      fillOpacity: 0.9,
      weight: 2,
    })
      .bindPopup(textPopup(point.label))
      .addTo(map);
    if (point.kind === "incoming") {
      incoming = latlng;
    }
  });
  points.forEach(function (point) {
    var lat = Number(point.lat);
    var lon = Number(point.lon);
    if (point.kind === "candidate" && incoming && Number.isFinite(lat) && Number.isFinite(lon)) {
      L.polyline([incoming, [lat, lon]], {
        color: "#888",
        weight: 2,
        dashArray: "6 6",
      }).addTo(map);
    }
  });
  if (!bounds.length) {
    map.remove();
    return;
  }
  if (bounds.length === 1) {
    map.setView(bounds[0], 16);
  } else {
    map.fitBounds(bounds, { padding: [28, 28], maxZoom: 17 });
  }
});
