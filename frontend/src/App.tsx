import { Routes, Route } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import PageContainer from './components/layout/PageContainer'
import Loading from './components/common/Loading'

// Lazy load pages for better performance
const HomePage = lazy(() => import('./pages/HomePage'))
const UploadPage = lazy(() => import('./pages/UploadPage'))
const StoryPage = lazy(() => import('./pages/StoryPage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const InteractiveStoryPage = lazy(() => import('./pages/InteractiveStoryPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const NewsPage = lazy(() => import('./pages/NewsPage'))

function App() {
  return (
    <Suspense fallback={<Loading fullScreen message="Loading..." />}>
      <Routes>
        {/* Auth routes (no page container) */}
        <Route path="/login" element={<LoginPage />} />

        {/* Main app routes */}
        <Route path="/" element={<PageContainer />}>
          <Route index element={<HomePage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="story/:storyId" element={<StoryPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="interactive" element={<InteractiveStoryPage />} />
          <Route path="news" element={<NewsPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default App
