import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import CameraCapture from '@/components/upload/CameraCapture'
import ParentConsentGate from '@/components/common/ParentConsentGate'
import useChildStore from '@/store/useChildStore'
import type { AgeGroup } from '@/types/api'

export const TOUCH_DEVICE_QUERY = '(pointer: coarse) and (max-width: 1024px)'

export type PickerTab = 'camera' | 'file'

interface ImageUploaderProps {
  onFileSelect: (file: File) => void
  accept?: Record<string, string[]>
  maxSize?: number
  className?: string
  /** When present together with ageGroup, enables the full CameraCapture
   *  experience (live preview + consent gate). When absent, the camera
   *  tab uses the quick-win `capture="environment"` fallback that ships
   *  with PR #589 — preserves backwards compatibility for legacy callers.
   */
  childId?: string
  ageGroup?: AgeGroup
}

export function pickInitialTab(isTouchSmall: boolean): PickerTab {
  return isTouchSmall ? 'camera' : 'file'
}

function ImageUploader({
  onFileSelect,
  accept = {
    'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.webp'],
  },
  maxSize = 10 * 1024 * 1024, // 10MB
  className = '',
  childId,
  ageGroup,
}: ImageUploaderProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFileSelect(acceptedFiles[0])
      }
    },
    [onFileSelect]
  )

  const { getRootProps, getInputProps, isDragActive, isDragReject, fileRejections } =
    useDropzone({
      onDrop,
      accept,
      maxSize,
      multiple: false,
    })

  const hasError = fileRejections.length > 0

  const [isTouchSmall, setIsTouchSmall] = useState(false)
  const cameraInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia(TOUCH_DEVICE_QUERY)
    const update = () => setIsTouchSmall(mq.matches)
    update()
    mq.addEventListener('change', update)
    return () => mq.removeEventListener('change', update)
  }, [])

  // Full camera experience requires both childId (for consent) and ageGroup
  // (for gate copy). Without them we fall back to the OS-camera quick-win.
  const fullCameraEnabled = Boolean(childId && ageGroup)

  const [activeTab, setActiveTab] = useState<PickerTab>(() => pickInitialTab(false))
  useEffect(() => {
    if (fullCameraEnabled) setActiveTab(pickInitialTab(isTouchSmall))
  }, [fullCameraEnabled, isTouchSmall])

  // Quick-win (no childId) path: legacy "Take Photo" button + dropzone.
  const handleCameraClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    cameraInputRef.current?.click()
  }

  const handleCameraChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && file.size <= maxSize) {
      onFileSelect(file)
    }
    if (cameraInputRef.current) cameraInputRef.current.value = ''
  }

  // Consent gate state (only relevant when fullCameraEnabled).
  const currentChild = useChildStore((s) => s.currentChild)
  const cameraConsent = useMemo(() => {
    if (!fullCameraEnabled) return true
    if (currentChild?.child_id !== childId) return false
    return currentChild?.camera_consent === true
  }, [fullCameraEnabled, currentChild, childId])

  const [showConsentGate, setShowConsentGate] = useState(false)

  function handleSelectCameraTab() {
    setActiveTab('camera')
    if (fullCameraEnabled && !cameraConsent) {
      setShowConsentGate(true)
    }
  }

  function handleCameraCapture(file: File) {
    onFileSelect(file)
  }

  const renderDropzone = () => (
    <motion.div
      whileHover={{ scale: 1.01 }}
      transition={{ duration: 0.2 }}
    >
      <div
        {...getRootProps()}
        className={`
          upload-zone
          ${isDragActive && !isDragReject ? 'upload-zone-active' : ''}
          ${isDragReject || hasError ? 'border-red-400 bg-red-50' : ''}
        `}
      >
        <input {...getInputProps()} />

        <AnimatePresence mode="wait">
          {isDragActive && !isDragReject ? (
            <motion.div
              key="drag"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="flex flex-col items-center gap-4"
            >
              <motion.span
                className="text-6xl"
                animate={{ y: [0, -10, 0] }}
                transition={{ duration: 0.5, repeat: Infinity }}
              >
                🎯
              </motion.span>
              <p className="text-xl font-bold text-primary">Drop to upload</p>
            </motion.div>
          ) : isDragReject ? (
            <motion.div
              key="reject"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-4"
            >
              <span className="text-6xl">😅</span>
              <p className="text-xl font-bold text-red-500">Unsupported file format</p>
              <p className="text-gray-500">Please upload PNG, JPG or GIF images</p>
            </motion.div>
          ) : (
            <motion.div
              key="default"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-4"
            >
              <div className="relative">
                <motion.span
                  className="text-6xl"
                  animate={{ rotate: [0, -5, 5, 0] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  🖼️
                </motion.span>
                <motion.span
                  className="absolute -top-2 -right-2 text-2xl"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  ✨
                </motion.span>
              </div>

              <div className="text-center">
                <p className="text-xl font-bold text-gray-700 mb-2">
                  {isTouchSmall ? 'Or pick from your photos' : 'Drag image here'}
                </p>
                <p className="text-gray-500">
                  {isTouchSmall ? 'Tap to choose a file' : 'or click to select file'}
                </p>
              </div>

              <div className="flex items-center gap-2 text-sm text-gray-400 mt-2">
                <span>Supports PNG, JPG, GIF</span>
                <span>•</span>
                <span>Max 10MB</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )

  // Legacy (no childId) quick-win path: show OS-camera button + dropzone.
  if (!fullCameraEnabled) {
    return (
      <div className={className}>
        {isTouchSmall && (
          <>
            <motion.button
              type="button"
              onClick={handleCameraClick}
              whileTap={{ scale: 0.97 }}
              className="w-full mb-3 py-4 px-6 rounded-2xl bg-primary text-white font-bold text-lg flex items-center justify-center gap-2 shadow-md"
              aria-label="Take a photo with your camera"
            >
              <span className="text-2xl" aria-hidden="true">📸</span>
              <span>Take Photo</span>
            </motion.button>
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={handleCameraChange}
              aria-hidden="true"
              tabIndex={-1}
            />
          </>
        )}

        {renderDropzone()}

        {hasError && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3 p-3 bg-red-100 rounded-lg text-red-600 text-sm"
          >
            {fileRejections[0]?.errors[0]?.message === 'File is larger than 10485760 bytes'
              ? 'File too large, please select an image under 10MB'
              : 'Upload error, please select another image'}
          </motion.div>
        )}
      </div>
    )
  }

  // Full-camera path: tabbed picker + consent gate.
  return (
    <div className={className}>
      <div
        role="tablist"
        aria-label="Image source"
        className="mb-3 inline-flex rounded-full bg-gray-100 p-1"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'camera'}
          onClick={handleSelectCameraTab}
          className={`px-4 py-2 rounded-full text-sm font-semibold transition-colors ${
            activeTab === 'camera' ? 'bg-white text-primary shadow' : 'text-gray-600'
          }`}
        >
          📸 Take Photo
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'file'}
          onClick={() => setActiveTab('file')}
          className={`px-4 py-2 rounded-full text-sm font-semibold transition-colors ${
            activeTab === 'file' ? 'bg-white text-primary shadow' : 'text-gray-600'
          }`}
        >
          📂 Upload File
        </button>
      </div>

      {activeTab === 'camera' ? (
        cameraConsent ? (
          <CameraCapture
            onCapture={handleCameraCapture}
            onCancel={() => setActiveTab('file')}
          />
        ) : (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-center">
            <p className="mb-3 text-amber-800">
              Ask a grown-up to allow the camera before you take a photo.
            </p>
            <button
              type="button"
              onClick={() => setShowConsentGate(true)}
              className="rounded-xl bg-amber-600 px-4 py-2 font-semibold text-white"
            >
              Ask permission
            </button>
          </div>
        )
      ) : (
        renderDropzone()
      )}

      {hasError && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-3 p-3 bg-red-100 rounded-lg text-red-600 text-sm"
        >
          {fileRejections[0]?.errors[0]?.message === 'File is larger than 10485760 bytes'
            ? 'File too large, please select an image under 10MB'
            : 'Upload error, please select another image'}
        </motion.div>
      )}

      {showConsentGate && fullCameraEnabled && ageGroup && childId && (
        <ParentConsentGate
          kind="camera"
          ageGroup={ageGroup}
          childId={childId}
          onGranted={() => setShowConsentGate(false)}
          onDismiss={() => {
            setShowConsentGate(false)
            setActiveTab('file')
          }}
        />
      )}
    </div>
  )
}

export default ImageUploader
