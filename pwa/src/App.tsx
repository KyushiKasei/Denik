import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AboutPage } from "./pages/AboutPage";
import { CatalogPage } from "./pages/CatalogPage";
import { DiaryPage } from "./pages/DiaryPage";
import { ImportPage } from "./pages/ImportPage";
import { MapPage } from "./pages/MapPage";
import { PlaceDetailPage } from "./pages/PlaceDetailPage";
import { TodayPage } from "./pages/TodayPage";
import { YearbookPage } from "./pages/YearbookPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<TodayPage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/diary" element={<DiaryPage />} />
          <Route path="/yearbook" element={<YearbookPage />} />
          <Route path="/place/:id" element={<PlaceDetailPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/info" element={<AboutPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
