import { Routes, Route, Navigate, useParams } from "react-router-dom";
import { Suspense, lazy } from "react";
import PageContainer from "./components/layout/PageContainer";
import Loading from "./components/common/Loading";
import { AudioProvider } from "./contexts/AudioContext";

// Lazy load pages for better performance
const HomePage = lazy(() => import("./pages/HomePage"));
const UploadPage = lazy(() => import("./pages/UploadPage"));
const StoryPage = lazy(() => import("./pages/StoryPage"));
const LibraryPage = lazy(() => import("./pages/LibraryPage"));
const InteractiveStoryPage = lazy(() => import("./pages/InteractiveStoryPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const ParentApprovalPage = lazy(() => import("./pages/ParentApprovalPage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const MyAgentPage = lazy(() => import("./pages/MyAgentPage"));
const ContentHubPage = lazy(() => import("./pages/ContentHubPage"));
const GroupPage = lazy(() => import("./pages/GroupPage"));
const KidsDailyPage = lazy(() => import("./pages/KidsDailyPage"));
const KidsDailyEpisodePage = lazy(
  () => import("./pages/KidsDailyEpisodePage"),
);

function RedirectKidsDailyEpisode({ paramName }: { paramName: string }) {
  const params = useParams();
  const id = params[paramName];
  return <Navigate to={`/kids-daily/${id ?? ""}`} replace />;
}

function App() {
  return (
    <AudioProvider>
      <Suspense fallback={<Loading fullScreen message="Loading..." />}>
        <Routes>
          {/* Auth routes (no page container) */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/parent-approval" element={<ParentApprovalPage />} />

          {/* Main app routes */}
          <Route path="/" element={<PageContainer />}>
            <Route index element={<HomePage />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="story/:storyId" element={<StoryPage />} />
            {/* /history redirects to /library for backwards compatibility */}
            <Route
              path="history"
              element={<Navigate to="/library" replace />}
            />
            <Route path="library" element={<LibraryPage />} />
            <Route path="interactive" element={<InteractiveStoryPage />} />

            {/* Kids Daily — canonical routes */}
            <Route path="kids-daily" element={<KidsDailyPage />} />
            <Route
              path="kids-daily/:episodeId"
              element={<KidsDailyEpisodePage />}
            />

            {/* Legacy URL redirects — preserve old bookmarks */}
            <Route
              path="news"
              element={<Navigate to="/kids-daily" replace />}
            />
            <Route
              path="news/:conversionId"
              element={<RedirectKidsDailyEpisode paramName="conversionId" />}
            />
            <Route
              path="morning-show"
              element={<Navigate to="/kids-daily" replace />}
            />
            <Route
              path="morning-show/subscriptions"
              element={<Navigate to="/kids-daily" replace />}
            />
            <Route
              path="morning-show/:episodeId"
              element={<RedirectKidsDailyEpisode paramName="episodeId" />}
            />

            <Route path="profile" element={<ProfilePage />} />
            <Route path="my-agent" element={<MyAgentPage />} />
            <Route path="content-hub" element={<ContentHubPage />} />
            <Route path="content-hub/:slug" element={<GroupPage />} />
          </Route>
        </Routes>
      </Suspense>
    </AudioProvider>
  );
}

export default App;
