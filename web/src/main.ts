import { Chat } from "./chat";
import "./style.css";

const root = document.getElementById("app");
if (root) void new Chat(root).start();
