import { initializeApp, type FirebaseApp } from 'firebase/app'
import {
  GoogleAuthProvider,
  getAuth,
  signInWithPopup,
  signOut,
  type Auth,
} from 'firebase/auth'
import { env, isFirebaseConfigured } from './env'

let firebaseApp: FirebaseApp | null = null
let firebaseAuth: Auth | null = null
let googleProvider: GoogleAuthProvider | null = null

function getFirebaseApp(): FirebaseApp {
  if (!isFirebaseConfigured()) {
    throw new Error('Firebase web configuration is missing in frontend environment')
  }

  if (!firebaseApp) {
    firebaseApp = initializeApp({
      apiKey: env.firebaseApiKey,
      authDomain: env.firebaseAuthDomain,
      projectId: env.firebaseProjectId,
      appId: env.firebaseAppId,
    })
  }

  return firebaseApp
}

function getFirebaseAuth(): Auth {
  if (!firebaseAuth) {
    firebaseAuth = getAuth(getFirebaseApp())
  }

  return firebaseAuth
}

function getGoogleProvider(): GoogleAuthProvider {
  if (!googleProvider) {
    googleProvider = new GoogleAuthProvider()
    googleProvider.setCustomParameters({
      prompt: 'select_account',
    })
  }

  return googleProvider
}

export async function signInWithGoogle(): Promise<string> {
  const result = await signInWithPopup(getFirebaseAuth(), getGoogleProvider())
  return result.user.getIdToken()
}

export async function signOutFromGoogle(): Promise<void> {
  if (!firebaseAuth) {
    return
  }

  await signOut(firebaseAuth)
}
