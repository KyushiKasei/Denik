import { lazy, Suspense, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { getPlace, getPlaceSnapshot, loadPlaces } from "../catalog/importCatalog";
import {
  appleMapsUrl,
  conditionLabel,
  displayPlaceName,
  feeLabel,
  formatGps,
  formatTypes,
  googleMapsUrl,
  hasGps,
  heritageLabel,
  locationLine,
  mapyCzUrl,
  parkingLabel,
  amenitiesLine,
  dogsLabel,
  paymentLabel,
  publicDescription,
  styleLine,
  phoneHref,
  visitabilityLabel,
  wheelchairLabel,
} from "../catalog/labels";
import type { CatalogPlace, PlaceNameSnapshot } from "../catalog/types";
import { PlaceJournal } from "../components/PlaceJournal";
import { HoursBadge } from "../components/HoursBadge";
import { RouteLinks } from "../components/RouteLinks";
import { hoursLineForPlace } from "../catalog/openingHours";
import { isOrphanPlace } from "../diary/orphans";
import { loadStoredMapView } from "../geo/mapOriginStore";
import { loadVisits } from "../diary/store";
import { similarPlaces } from "../diary/similarPlaces";
import { PlaceCard } from "../components/PlaceCard";

const PlaceMap = lazy(async () => {
  const module = await import("../components/PlaceMap");
  return { default: module.PlaceMap };
});

const LINK_LABELS: Array<[keyof CatalogPlace["links"], string]> = [
  ["official", "Oficiální web"],
  ["opening_hours", "Otevírací doba"],
  ["tickets", "Vstupenky"],
  ["wikipedia", "Wikipedia"],
  ["wikidata", "Wikidata"],
  ["heritage_catalog", "Památkový katalog"],
];

function cameFrom(
  searchParams: URLSearchParams,
  state: unknown,
  page: "map" | "diary" | "today",
): boolean {
  if (searchParams.get("from") === page) {
    return true;
  }
  if (state && typeof state === "object" && "from" in state && (state as { from?: string }).from === page) {
    return true;
  }
  if (page === "map" && typeof document !== "undefined" && /\/map(\?|#|$)/.test(document.referrer)) {
    return true;
  }
  if (page === "diary" && typeof document !== "undefined" && /\/diary(\?|#|$)/.test(document.referrer)) {
    return true;
  }
  if (page === "today" && typeof document !== "undefined" && /\/(\?|#|$)/.test(document.referrer)) {
    return true;
  }
  return false;
}

function BackLink({ fromMap, fromDiary, fromToday }: { fromMap: boolean; fromDiary: boolean; fromToday: boolean }) {
  const navigate = useNavigate();
  const label = fromMap ? "← Mapa" : fromDiary ? "← Deník" : fromToday ? "← Dnes" : "← Katalog";
  const fallback = fromMap ? "/map" : fromDiary ? "/diary" : fromToday ? "/" : "/catalog";
  return (
    <p className="back">
      <button
        type="button"
        className="text-link"
        onClick={() => {
          if (window.history.length > 1) {
            navigate(-1);
            return;
          }
          navigate(fallback);
        }}
      >
        {label}
      </button>
    </p>
  );
}

export function PlaceDetailPage() {
  const { id } = useParams();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const fromMap = cameFrom(searchParams, location.state, "map");
  const fromDiary = cameFrom(searchParams, location.state, "diary");
  const fromToday = cameFrom(searchParams, location.state, "today");
  const [place, setPlace] = useState<CatalogPlace | null | undefined>(undefined);
  const [similar, setSimilar] = useState<CatalogPlace[]>([]);
  const [orphan, setOrphan] = useState(false);
  const [snapshot, setSnapshot] = useState<PlaceNameSnapshot | undefined>(undefined);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [routeOrigin, setRouteOrigin] = useState<{ latitude: number; longitude: number } | null>(null);

  useEffect(() => {
    if (!id) {
      setPlace(null);
      setOrphan(false);
      setSnapshot(undefined);
      setLoadError(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const row = await getPlace(id);
        if (cancelled) {
          return;
        }
        if (row) {
          setPlace(row);
          setOrphan(false);
          setSnapshot(undefined);
          setLoadError(null);
          const [catalog, visits] = await Promise.all([loadPlaces(), loadVisits()]);
          if (!cancelled) {
            setSimilar(similarPlaces(row, catalog, visits));
          }
          return;
        }
        const [orphaned, lastKnown] = await Promise.all([isOrphanPlace(id), getPlaceSnapshot(id)]);
        if (cancelled) {
          return;
        }
        setPlace(null);
        setOrphan(orphaned);
        setSnapshot(lastKnown);
        setLoadError(null);
      } catch {
        if (!cancelled) {
          setLoadError("Místo se nepodařilo načíst.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    const stored = loadStoredMapView();
    if (stored) {
      setRouteOrigin({ latitude: stored.latitude, longitude: stored.longitude });
    }
  }, []);

  if (loadError) {
    return (
      <p className="error" role="alert">
        {loadError}
      </p>
    );
  }

  if (place === undefined) {
    return <p className="muted">Načítám místo…</p>;
  }
  if (!place && orphan && id) {
    return (
      <article className="place-detail">
        <BackLink fromMap={fromMap} fromDiary={fromDiary} fromToday={fromToday} />
        <p className="orphan-banner" role="status">
          Místo už není v katalogu. Návštěvy zůstávají.
        </p>
        <h1>{snapshot?.name || "Místo už není v katalogu"}</h1>
        <p className="muted">
          {snapshot?.municipality ? `${snapshot.municipality} · ` : ""}
          Interní ID: <code>{id}</code>
        </p>
        <PlaceJournal placeId={id} />
        <p>
          <Link to="/catalog">Zpět na seznam</Link>
        </p>
      </article>
    );
  }
  if (!place) {
    return (
      <section>
        <p>Místo v katalogu není.</p>
        <p>
          <Link to="/catalog">Zpět na seznam</Link>
        </p>
      </section>
    );
  }

  const gps = formatGps(place);
  const hoursLine = hoursLineForPlace(place);
  const phone = phoneHref(place.phone);
  const fee = feeLabel(place.fee);
  const wheelchair = wheelchairLabel(place.wheelchair);
  const parking = parkingLabel(place.parking);
  const dogs = dogsLabel(place.dogs);
  const payment = paymentLabel(place.payment);
  const amenities = amenitiesLine(place);
  const style = styleLine(place);
  const mapy = mapyCzUrl(place);
  const gmaps = googleMapsUrl(place);
  const apple = appleMapsUrl(place);
  const links = LINK_LABELS.filter(([key]) => place.links[key]);

  return (
    <article className="place-detail">
      <BackLink fromMap={fromMap} fromDiary={fromDiary} fromToday={fromToday} />
      <h1>{displayPlaceName(place.name)}</h1>
      {place.short_name ? <p className="muted">{place.short_name}</p> : null}
      {formatTypes(place.types, { hideInName: place.name }) ? (
        <p className="place-types">{formatTypes(place.types, { hideInName: place.name })}</p>
      ) : null}
      {locationLine(place) ? <p>{locationLine(place)}</p> : null}

      {place.image?.thumbnail_url ? (
        <figure className="place-photo">
          <img src={place.image.thumbnail_url} alt={place.name} />
          {place.image.attribution || place.image.license ? (
            <figcaption>
              {place.image.attribution}
              {place.image.license ? ` · ${place.image.license}` : ""}
              {place.image.license_url ? (
                <>
                  {" "}
                  <a href={place.image.license_url} target="_blank" rel="noreferrer">
                    licence
                  </a>
                </>
              ) : null}
            </figcaption>
          ) : null}
        </figure>
      ) : null}

      {publicDescription(place) ? <p>{publicDescription(place)}</p> : null}

      <PlaceJournal placeId={place.id} />

      <dl className="detail-grid">
        <dt>Stav</dt>
        <dd>{conditionLabel(place.condition)}</dd>
        <dt>Přístupnost</dt>
        <dd>
          {visitabilityLabel(place.visitability)}
          {" "}
          <HoursBadge place={place} />
        </dd>
        {hoursLine ? (
          <>
            <dt>Hodiny</dt>
            <dd>{hoursLine}</dd>
          </>
        ) : null}
        {place.phone ? (
          <>
            <dt>Telefon</dt>
            <dd>
              {phone ? <a href={phone}>{place.phone}</a> : place.phone}
            </dd>
          </>
        ) : null}
        {fee ? (
          <>
            <dt>Vstupné</dt>
            <dd>{fee}</dd>
          </>
        ) : null}
        {wheelchair ? (
          <>
            <dt>Bezbariérovost</dt>
            <dd>{wheelchair}</dd>
          </>
        ) : null}
        {parking ? (
          <>
            <dt>Parkování</dt>
            <dd>{parking}</dd>
          </>
        ) : null}
        {dogs ? (
          <>
            <dt>Psi</dt>
            <dd>{dogs}</dd>
          </>
        ) : null}
        {payment ? (
          <>
            <dt>Platba</dt>
            <dd>{payment}</dd>
          </>
        ) : null}
        {amenities ? (
          <>
            <dt>Zázemí</dt>
            <dd>{amenities}</dd>
          </>
        ) : null}
        {style ? (
          <>
            <dt>Sloh</dt>
            <dd>{style}</dd>
          </>
        ) : null}
        <dt>Ochrana</dt>
        <dd>{heritageLabel(place.heritage_status)}</dd>
        <dt>UNESCO</dt>
        <dd>{place.unesco ? "ano" : "ne"}</dd>
        {place.location.address ? (
          <>
            <dt>Adresa</dt>
            <dd>{place.location.address}</dd>
          </>
        ) : null}
        <dt>GPS</dt>
        <dd>{gps ?? "chybí"}</dd>
        {place.osm_opening_hours && !hoursLine ? (
          <>
            <dt>OSM hodiny</dt>
            <dd>{place.osm_opening_hours}</dd>
          </>
        ) : null}
      </dl>

      {place.alternative_names.length > 0 ? (
        <p className="muted">Další názvy: {place.alternative_names.join(", ")}</p>
      ) : null}

      {hasGps(place) && place.location.latitude != null && place.location.longitude != null ? (
        <section>
          <h2>Mapa</h2>
          <Suspense fallback={<p className="muted">Načítám mapu…</p>}>
            <PlaceMap latitude={place.location.latitude} longitude={place.location.longitude} name={place.name} />
          </Suspense>
          <p className="map-links">
            {mapy ? (
              <a href={mapy} target="_blank" rel="noreferrer">
                Mapy.cz
              </a>
            ) : null}
            {gmaps ? (
              <a href={gmaps} target="_blank" rel="noreferrer">
                Google Maps
              </a>
            ) : null}
            {apple ? (
              <a href={apple} target="_blank" rel="noreferrer">
                Apple Maps
              </a>
            ) : null}
          </p>
          <RouteLinks
            dest={{ latitude: place.location.latitude, longitude: place.location.longitude }}
            destName={place.name}
            origin={routeOrigin}
            promptMap
          />
          <p className="muted small">Mapové dlaždice se berou ze sítě nebo z naposledy stažených výřezů. Celé Česko tu není.</p>
        </section>
      ) : (
        <p className="muted">Souřadnice chybí, místo je jen v seznamu.</p>
      )}

      {similar.length > 0 ? (
        <section className="today-block">
          <h2>Podobná místa</h2>
          <div className="place-cards">
            {similar.map((row) => (
              <PlaceCard key={row.id} place={row} to={`/place/${row.id}?from=today`} />
            ))}
          </div>
        </section>
      ) : null}

      {links.length > 0 ? (
        <section>
          <h2>Odkazy</h2>
          <ul className="link-list">
            {links.map(([key, label]) => (
              <li key={key}>
                <a href={place.links[key] ?? undefined} target="_blank" rel="noreferrer">
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
