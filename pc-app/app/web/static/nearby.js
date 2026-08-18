(function () {
  let map = null;
  let layoutTimer = 0;
  let resizeObserver = null;
  let atlasById = {};
  let atlasTimeline = [];
  let atlasCursor = "today";
  let atlasPlaying = false;
  let atlasPlayTimer = 0;
  let atlasUntil = null;
  let timeControlsBound = false;

  const CZECH_BOUNDS = [
    [48.55, 12.09],
    [51.06, 18.86],
  ];

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatVisitDate(visitedAt) {
    if (!visitedAt) {
      return "bez data";
    }
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(visitedAt);
    if (!match) {
      return visitedAt;
    }
    return Number(match[3]) + ". " + Number(match[2]) + ". " + match[1];
  }

  function timelineIndexForUntil(timeline, until) {
    if (!until) {
      return "today";
    }
    let last = -1;
    for (let i = 0; i < timeline.length; i++) {
      const at = timeline[i].visited_at;
      if (at && at <= until) {
        last = i;
      }
    }
    return last;
  }

  function atlasYears(timeline) {
    const years = [];
    const seen = {};
    for (let i = 0; i < timeline.length; i++) {
      const at = timeline[i].visited_at;
      if (!at || !/^\d{4}/.test(at)) {
        continue;
      }
      const year = at.slice(0, 4);
      if (!seen[year]) {
        seen[year] = true;
        years.push(year);
      }
    }
    return years;
  }

  function lastIndexForYear(timeline, year) {
    return timelineIndexForUntil(timeline, year + "-12-31");
  }

  function atlasCaption(timeline, cursor) {
    if (cursor === "today") {
      return "Dnes";
    }
    if (typeof cursor !== "number" || cursor < 0 || !timeline[cursor]) {
      return "Začátek";
    }
    const event = timeline[cursor];
    return formatVisitDate(event.visited_at) + " · " + event.name;
  }

  function stopAtlasPlay() {
    atlasPlaying = false;
    if (atlasPlayTimer) {
      clearInterval(atlasPlayTimer);
      atlasPlayTimer = 0;
    }
    const playBtn = document.getElementById("atlas-time-play");
    if (playBtn) {
      playBtn.textContent = "Přehrát";
      playBtn.classList.remove("active");
    }
  }

  function clearUntilFromUrl() {
    const url = new URL(window.location.href);
    if (!url.searchParams.has("until")) {
      return;
    }
    url.searchParams.delete("until");
    history.replaceState(null, "", url.pathname + url.search + url.hash);
    const hidden = document.querySelector("#nearby-form input[name=until]");
    if (hidden) {
      hidden.remove();
    }
    atlasUntil = null;
  }

  function destroyMap() {
    stopAtlasPlay();
    atlasById = {};
    atlasTimeline = [];
    if (layoutTimer) {
      clearTimeout(layoutTimer);
      layoutTimer = 0;
    }
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
    if (map) {
      map.remove();
      map = null;
    }
  }

  function readMapData() {
    const node = document.getElementById("nearby-map-data");
    if (!node) {
      return null;
    }
    try {
      return JSON.parse(node.textContent || "");
    } catch (_err) {
      return null;
    }
  }

  function visiblePlaceIds(cursor) {
    if (cursor === "today") {
      return null;
    }
    const ids = {};
    if (typeof cursor === "number" && cursor >= 0) {
      for (let i = 0; i <= cursor && i < atlasTimeline.length; i++) {
        ids[atlasTimeline[i].id] = true;
      }
    }
    return ids;
  }

  function applyAtlasCursor(cursor) {
    atlasCursor = cursor;
    if (!map) {
      return;
    }
    const ids = visiblePlaceIds(cursor);
    const activeId =
      cursor !== "today" && typeof cursor === "number" && cursor >= 0 && atlasTimeline[cursor]
        ? atlasTimeline[cursor].id
        : null;
    Object.keys(atlasById).forEach(function (id) {
      const entry = atlasById[id];
      const show = ids === null ? true : Boolean(ids[id]);
      if (show) {
        if (!map.hasLayer(entry.marker)) {
          entry.marker.addTo(map);
        }
      } else if (map.hasLayer(entry.marker)) {
        map.removeLayer(entry.marker);
      }
      const active = activeId === id;
      entry.marker.setRadius(active ? 11 : entry.kind === "visited" ? 8 : 6);
      entry.marker.setStyle({ weight: active ? 3 : entry.kind === "visited" ? 2 : 1 });
    });
    updateTimeUi();
  }

  function updateTimeUi() {
    const wrap = document.getElementById("atlas-time");
    const caption = document.getElementById("atlas-time-caption");
    const slider = document.getElementById("atlas-time-range");
    const wantLegend = document.getElementById("atlas-legend-want");
    const prevBtn = document.getElementById("atlas-time-prev");
    const nextBtn = document.getElementById("atlas-time-next");
    const todayBtn = document.getElementById("atlas-time-today");
    if (!wrap) {
      return;
    }
    if (!atlasTimeline.length) {
      wrap.hidden = true;
      if (wantLegend) {
        wantLegend.hidden = false;
      }
      return;
    }
    wrap.hidden = false;
    const last = atlasTimeline.length - 1;
    if (caption) {
      caption.textContent = atlasCaption(atlasTimeline, atlasCursor);
    }
    if (slider) {
      slider.max = String(last);
      slider.value = String(atlasCursor === "today" ? last : Math.max(0, atlasCursor));
      slider.setAttribute("aria-valuetext", atlasCaption(atlasTimeline, atlasCursor));
    }
    if (wantLegend) {
      wantLegend.hidden = atlasCursor !== "today";
    }
    if (prevBtn) {
      prevBtn.disabled = atlasCursor !== "today" && atlasCursor <= 0;
    }
    if (nextBtn) {
      nextBtn.disabled = atlasCursor === "today";
    }
    if (todayBtn) {
      todayBtn.disabled = atlasCursor === "today";
    }
    const yearWrap = document.getElementById("atlas-time-years");
    if (yearWrap) {
      const currentYear =
        atlasCursor === "today" || atlasCursor < 0
          ? ""
          : (atlasTimeline[atlasCursor].visited_at || "").slice(0, 4);
      Array.prototype.forEach.call(yearWrap.querySelectorAll("button"), function (btn) {
        btn.classList.toggle("active", btn.getAttribute("data-year") === currentYear);
      });
    }
  }

  function fillYearButtons() {
    const yearWrap = document.getElementById("atlas-time-years");
    if (!yearWrap) {
      return;
    }
    yearWrap.innerHTML = "";
    atlasYears(atlasTimeline).forEach(function (year) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = year;
      btn.setAttribute("data-year", year);
      btn.addEventListener("click", function () {
        stopAtlasPlay();
        applyAtlasCursor(lastIndexForYear(atlasTimeline, year));
      });
      yearWrap.appendChild(btn);
    });
  }

  function stepAtlas(delta) {
    stopAtlasPlay();
    const last = atlasTimeline.length - 1;
    if (delta < 0) {
      if (atlasCursor === "today") {
        applyAtlasCursor(last);
        return;
      }
      if (typeof atlasCursor === "number" && atlasCursor > 0) {
        applyAtlasCursor(atlasCursor - 1);
      }
      return;
    }
    if (atlasCursor === "today") {
      return;
    }
    if (typeof atlasCursor === "number" && atlasCursor < last) {
      applyAtlasCursor(atlasCursor + 1);
      return;
    }
    applyAtlasCursor("today");
    clearUntilFromUrl();
  }

  function goAtlasToday() {
    stopAtlasPlay();
    applyAtlasCursor("today");
    clearUntilFromUrl();
  }

  function toggleAtlasPlay() {
    if (atlasPlaying) {
      stopAtlasPlay();
      return;
    }
    if (!atlasTimeline.length) {
      return;
    }
    if (atlasCursor === "today" || (typeof atlasCursor === "number" && atlasCursor >= atlasTimeline.length - 1)) {
      applyAtlasCursor(0);
    }
    atlasPlaying = true;
    const playBtn = document.getElementById("atlas-time-play");
    if (playBtn) {
      playBtn.textContent = "Pauza";
      playBtn.classList.add("active");
    }
    atlasPlayTimer = setInterval(function () {
      const last = atlasTimeline.length - 1;
      if (atlasCursor === "today") {
        stopAtlasPlay();
        return;
      }
      if (typeof atlasCursor === "number" && atlasCursor < last) {
        applyAtlasCursor(atlasCursor + 1);
        return;
      }
      applyAtlasCursor("today");
      clearUntilFromUrl();
      stopAtlasPlay();
    }, 500);
  }

  function bindTimeControls() {
    if (timeControlsBound) {
      return;
    }
    timeControlsBound = true;
    const slider = document.getElementById("atlas-time-range");
    const prevBtn = document.getElementById("atlas-time-prev");
    const nextBtn = document.getElementById("atlas-time-next");
    const playBtn = document.getElementById("atlas-time-play");
    const todayBtn = document.getElementById("atlas-time-today");
    if (slider) {
      slider.addEventListener("input", function () {
        stopAtlasPlay();
        applyAtlasCursor(Number(slider.value));
      });
    }
    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        stepAtlas(-1);
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        stepAtlas(1);
      });
    }
    if (playBtn) {
      playBtn.addEventListener("click", toggleAtlasPlay);
    }
    if (todayBtn) {
      todayBtn.addEventListener("click", goAtlasToday);
    }
  }

  function initMap(el, data) {
    destroyMap();
    if (!el || !data || typeof L === "undefined") {
      return;
    }
    const isAtlas = data.mode === "atlas";
    const lat = Number(data.lat);
    const lon = Number(data.lon);
    const radiusKm = Number(data.radius);
    if (!isAtlas && (!Number.isFinite(lat) || !Number.isFinite(lon))) {
      return;
    }
    const iconBase = "/static/vendor/leaflet/images/";
    L.Icon.Default.mergeOptions({
      iconUrl: iconBase + "marker-icon.png",
      iconRetinaUrl: iconBase + "marker-icon-2x.png",
      shadowUrl: iconBase + "marker-shadow.png",
    });
    const markers = Array.isArray(data.markers) ? data.markers : [];
    const instance = L.map(el, {
      zoomControl: true,
      scrollWheelZoom: true,
      center: [Number.isFinite(lat) ? lat : 49.817, Number.isFinite(lon) ? lon : 15.473],
      zoom: isAtlas ? 7 : 11,
    });
    map = instance;
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19,
    }).addTo(instance);
    tiles.on("tileerror", function () {
      const wrap = document.getElementById("nearby-map-wrap");
      if (!wrap || wrap.querySelector(".nearby-map-error")) {
        return;
      }
      const note = document.createElement("p");
      note.className = "muted nearby-map-error";
      note.textContent = "Mapové podklady se nenačetly. Značky míst z katalogu by měly jít vidět.";
      wrap.appendChild(note);
    });
    let circle = null;
    if (!isAtlas) {
      L.marker([lat, lon]).addTo(instance).bindPopup("Tady");
      circle = L.circle([lat, lon], {
        radius: radiusKm * 1000,
        color: "#3d5a40",
        fillOpacity: 0.08,
      }).addTo(instance);
    }
    const drawn = [];
    markers.forEach(function (item) {
      if (item.lat == null || item.lon == null) {
        return;
      }
      const color = item.color || (item.visited ? "#3d5a40" : item.want ? "#c9a227" : "#6a6258");
      const kind = item.kind || (item.visited ? "visited" : item.want ? "want" : "other");
      const marker = L.circleMarker([item.lat, item.lon], {
        radius: kind === "visited" ? 8 : 6,
        color: color,
        fillColor: color,
        fillOpacity: kind === "other" ? 0.45 : 0.9,
        weight: kind === "visited" ? 2 : 1,
      }).addTo(instance);
      drawn.push(marker);
      if (isAtlas) {
        atlasById[item.id] = { marker: marker, kind: kind };
      }
      const kmPart =
        item.km == null || item.km === ""
          ? ""
          : "<br>" + Number(item.km).toFixed(1) + " km";
      marker.bindPopup(
        "<a href=\"/places/" +
          encodeURIComponent(item.id) +
          "\">" +
          escapeHtml(item.name) +
          "</a>" +
          kmPart
      );
    });

    function layout() {
      if (map !== instance || !el.isConnected) {
        return;
      }
      instance.invalidateSize();
      if (isAtlas) {
        if (drawn.length) {
          instance.fitBounds(L.featureGroup(drawn).getBounds(), { padding: [24, 24], maxZoom: 10 });
        } else {
          instance.fitBounds(CZECH_BOUNDS, { padding: [24, 24] });
        }
        return;
      }
      if (circle) {
        instance.fitBounds(circle.getBounds(), { padding: [16, 16], maxZoom: 14 });
      }
    }
    layout();
    requestAnimationFrame(function () {
      requestAnimationFrame(layout);
    });
    layoutTimer = setTimeout(layout, 200);
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(function () {
        if (map === instance) {
          instance.invalidateSize();
        }
      });
      resizeObserver.observe(el);
    }

    if (isAtlas) {
      atlasTimeline = Array.isArray(data.timeline) ? data.timeline : [];
      atlasUntil = data.until || null;
      fillYearButtons();
      applyAtlasCursor(timelineIndexForUntil(atlasTimeline, atlasUntil));
    }
  }

  function syncMap() {
    const wrap = document.getElementById("nearby-map-wrap");
    const el = document.getElementById("nearby-map");
    const data = readMapData();
    if (!wrap || !el || !data) {
      destroyMap();
      if (wrap) {
        wrap.hidden = true;
      }
      return;
    }
    wrap.hidden = false;
    initMap(el, data);
  }

  function resultsSwapped(event) {
    const target = event.detail && event.detail.target;
    return !!(target && target.id === "nearby-results");
  }

  function bind() {
    const form = document.getElementById("nearby-form");
    const slider = document.getElementById("nearby-radius");
    const label = document.getElementById("nearby-radius-label");
    const gpsBtn = document.getElementById("nearby-gps");
    if (slider && label) {
      slider.addEventListener("input", function () {
        label.textContent = slider.value;
      });
    }
    const qInput = document.getElementById("nearby-q");
    if (qInput) {
      qInput.addEventListener("input", function () {
        const lat = document.getElementById("nearby-lat");
        const lon = document.getElementById("nearby-lon");
        const originLabel = document.getElementById("nearby-origin-label");
        if (lat) lat.value = "";
        if (lon) lon.value = "";
        if (originLabel) originLabel.value = "";
      });
    }
    if (gpsBtn) {
      gpsBtn.addEventListener("click", function () {
        const errorEl = document.getElementById("nearby-gps-error");
        function showGpsError(message) {
          if (!errorEl) {
            return;
          }
          errorEl.hidden = !message;
          errorEl.textContent = message || "";
        }
        showGpsError("");
        if (!navigator.geolocation) {
          showGpsError("Prohlížeč GPS nenabízí. Zadejte obec, nebo souřadnice.");
          return;
        }
        gpsBtn.disabled = true;
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            const lat = document.getElementById("nearby-lat");
            const lon = document.getElementById("nearby-lon");
            if (lat && lon) {
              lat.value = pos.coords.latitude.toFixed(6);
              lon.value = pos.coords.longitude.toFixed(6);
            }
            const originLabel = document.getElementById("nearby-origin-label");
            if (originLabel) {
              originLabel.value = "Moje poloha";
            }
            gpsBtn.disabled = false;
            if (form) {
              form.requestSubmit();
            }
          },
          function (err) {
            gpsBtn.disabled = false;
            if (err && err.code === err.PERMISSION_DENIED) {
              showGpsError("Přístup k poloze byl odepřen. Zadejte obec, nebo souřadnice.");
              return;
            }
            showGpsError("Polohu se nepodařilo zjistit. Zadejte obec, nebo souřadnice.");
          }
        );
      });
    }
    document.body.addEventListener("click", function (event) {
      const link = event.target.closest("#nearby-suggest a");
      if (!link) {
        return;
      }
      const box = document.getElementById("nearby-suggest");
      if (box) {
        box.innerHTML = "";
      }
    });
    bindTimeControls();
    syncMap();
  }

  document.body.addEventListener("htmx:afterSettle", function (event) {
    if (resultsSwapped(event)) {
      syncMap();
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
