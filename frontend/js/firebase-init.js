import { initializeApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

// Configuracao do projeto Firebase (web). A API key de web app e PUBLICA por
// design (exposta no client) e nao e um segredo. Embute-la aqui elimina a
// dependencia de um arquivo separado (firebase-config.js) que podia ficar em
// cache obsoleto no service worker e quebrar o carregamento dos modulos.
const firebaseConfig = {
  apiKey: "AIzaSyBC0D_CdcPK_QBQ4vivZM4x6CDu_5yXW8o",
  authDomain: "valorpublico-b1e6d.firebaseapp.com",
  projectId: "valorpublico-b1e6d",
  storageBucket: "valorpublico-b1e6d.firebasestorage.app",
  messagingSenderId: "105223607610",
  appId: "1:105223607610:web:b49f0e79466614a81aac03",
  measurementId: "G-H0TT29Q651",
};

export const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);
