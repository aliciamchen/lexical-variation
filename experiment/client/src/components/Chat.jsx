import React, { useState, useEffect, useRef, useCallback } from "react";
import { usePlayer } from "@empirica/core/player/classic/react";
import { AVATAR_PLACEHOLDER } from "../constants";

// Typing indicator timing. Each `${group}_typing` write is a round trip to the
// server and a re-render for every group member, so a keystroke does not
// write more often than TYPING_WRITE_INTERVAL_MS: the first keystroke of a
// burst writes at once, later ones only once that long has passed. The
// "stopped" write goes out after TYPING_STOP_MS of silence, and readers treat
// a timestamp older than TYPING_STALE_MS as stopped anyway, so the interval
// must stay shorter than the stale window or the indicator would flicker.
export const TYPING_WRITE_INTERVAL_MS = 1500;
export const TYPING_STOP_MS = 2000;
export const TYPING_STALE_MS = 3000;

/**
 * Custom Chat component for the reference game experiment.
 *
 * This replaces the Empirica Chat component to:
 * - Support customPlayerName for role labels (Speaker/Listener)
 * - Fix timestamp display (5-second increments instead of all "now")
 * - Fix avatar display for DiceBear URLs
 * - Use square avatars to match the rest of the UI
 * - Show typing indicators for other players
 */
export function Chat({
  scope,
  attribute = "messages",
  customPlayerName,
  typingAttribute,
  groupPlayers = [],
}) {
  const player = usePlayer();

  if (!scope || !player) {
    return <Loading />;
  }

  const handleNewMessage = (text, composition = {}) => {
    const senderName = customPlayerName
      ? customPlayerName(player)
      : player.get("name") || player.id;

    // Atomic server-side append: two players sending at the same moment can no
    // longer overwrite each other (the previous read-modify-write of the whole
    // array could drop a message). The server still reads the attribute as an
    // array via stage.get(...).
    //
    // `composeStartedAt` and `pasted` describe how the message was produced.
    // Both come from the sender's own clock, so the composition interval is a
    // within-client difference and is unaffected by clock skew between
    // participants. Composition effort is a production measure alongside word
    // count, and a long message composed in almost no time is the clearest
    // signal that text was pasted in from elsewhere.
    scope.append(attribute, {
      id: `${player.id}-${Date.now()}`,
      text,
      timestamp: Date.now(),
      composeStartedAt: composition.composeStartedAt ?? null,
      pasted: Boolean(composition.pasted),
      sender: {
        id: player.id,
        name: senderName,
        avatar: player.get("avatar"),
      },
    });
  };

  const setTyping = useCallback(
    (isTyping) => {
      if (!typingAttribute) return;
      const current = scope.get(typingAttribute) || {};
      if (isTyping) {
        scope.set(typingAttribute, { ...current, [player.id]: Date.now() });
      } else {
        const { [player.id]: _, ...rest } = current;
        scope.set(typingAttribute, rest);
      }
    },
    [scope, typingAttribute, player.id]
  );

  const msgs = scope.get(attribute) || [];

  // Build typing names from scope state
  const typingNames = [];
  if (typingAttribute) {
    const typingState = scope.get(typingAttribute) || {};
    const now = Date.now();
    for (const [pid, timestamp] of Object.entries(typingState)) {
      if (pid === player.id) continue;
      if (now - timestamp > TYPING_STALE_MS) continue;
      const p = groupPlayers.find((gp) => gp.id === pid);
      if (p) {
        const name = customPlayerName ? customPlayerName(p) : p.get("name") || "Player";
        typingNames.push(name);
      }
    }
  }

  return (
    <div className="h-full w-full flex flex-col">
      <Messages msgs={msgs} />
      <TypingIndicator names={typingNames} />
      <Input onNewMessage={handleNewMessage} setTyping={setTyping} />
    </div>
  );
}

function Messages({ msgs }) {
  const scroller = useRef(null);
  const [msgCount, setMsgCount] = useState(0);

  useEffect(() => {
    if (!scroller.current) return;
    if (msgCount !== msgs.length) {
      setMsgCount(msgs.length);
      scroller.current.scrollTop = scroller.current.scrollHeight;
    }
  }, [scroller, msgs, msgCount]);

  if (msgs.length === 0) {
    return (
      <div className="h-full w-full flex justify-center items-center">
        <div className="flex flex-col justify-center items-center w-2/3 space-y-2">
          <div className="w-24 h-24 text-gray-200">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-full w-full fill-current"
              viewBox="0 0 512 512"
            >
              <path d="M123.6 391.3c12.9-9.4 29.6-11.8 44.6-6.4c26.5 9.6 56.2 15.1 87.8 15.1c124.7 0 208-80.5 208-160s-83.3-160-208-160S48 160.5 48 240c0 32 12.4 62.8 35.7 89.2c8.6 9.7 12.8 22.5 11.8 35.5c-1.4 18.1-5.7 34.7-11.3 49.4c17-7.9 31.1-16.7 39.4-22.7zM21.2 431.9c1.8-2.7 3.5-5.4 5.1-8.1c10-16.6 19.5-38.4 21.4-62.9C17.7 326.8 0 285.1 0 240C0 125.1 114.6 32 256 32s256 93.1 256 208s-114.6 208-256 208c-37.1 0-72.3-6.4-104.1-17.9c-11.9 8.7-31.3 20.6-54.3 30.6c-15.1 6.6-32.3 12.6-50.1 16.1c-.8 .2-1.6 .3-2.4 .5c-4.4 .8-8.7 1.5-13.2 1.9c-.2 0-.5 .1-.7 .1c-5.1 .5-10.2 .8-15.3 .8c-6.5 0-12.3-3.9-14.8-9.9c-2.5-6-1.1-12.8 3.4-17.4c4.1-4.2 7.8-8.7 11.3-13.5c1.7-2.3 3.3-4.6 4.8-6.9c.1-.2 .2-.3 .3-.5z" />
            </svg>
          </div>
          <h4 className="text-gray-700 font-semibold">No chat yet</h4>
          <p className="text-gray-500 text-center">
            Send a message to start the conversation.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-messages h-full overflow-auto pl-2 pr-4 pb-2" ref={scroller}>
      {msgs.map((msg) => (
        <MessageComp key={msg.id} msg={msg} />
      ))}
    </div>
  );
}

function MessageComp({ msg }) {
  const ts = msg.timestamp ? new Date(msg.timestamp) : new Date();

  // The sender's avatar, or a neutral placeholder. The fallback must not be
  // derived from the sender (it used to be a DiceBear identicon seeded on
  // msg.sender.id): that id is persistent, so in mixed Phase 2 it would have
  // rendered one stable image per player while the anonymous avatars around it
  // change every trial. See AVATAR_PLACEHOLDER in shared/constants.js.
  const avatar = msg.sender.avatar || AVATAR_PLACEHOLDER;

  return (
    <div className="flex items-start my-2">
      <div className="flex-shrink-0">
        <img
          className="inline-block h-9 w-9 rounded-md"
          src={avatar}
          alt={msg.sender.id}
        />
      </div>
      <div className="ml-3 text-sm">
        <p>
          <span className="font-semibold text-gray-900">{msg.sender.name}</span>
          <span className="pl-2 text-gray-400">{ts && relTime(ts)}</span>
        </p>
        <p className="text-gray-900">{msg.text}</p>
      </div>
    </div>
  );
}

function TypingIndicator({ names }) {
  if (names.length === 0) return null;

  const text =
    names.length === 1
      ? `${names[0]} is typing`
      : `${names.join(" and ")} are typing`;

  return (
    <div className="px-3 py-1 text-xs text-gray-400 flex items-center gap-1">
      <span>{text}</span>
      <span className="typing-dots">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </span>
      <style>{`
        .typing-dots {
          display: inline-flex;
          gap: 2px;
          align-items: center;
        }
        .typing-dot {
          width: 3px;
          height: 3px;
          border-radius: 50%;
          background-color: #9ca3af;
          animation: typing-pulse 1.4s infinite ease-in-out;
        }
        .typing-dot:nth-child(2) {
          animation-delay: 0.2s;
        }
        .typing-dot:nth-child(3) {
          animation-delay: 0.4s;
        }
        @keyframes typing-pulse {
          0%, 80%, 100% { opacity: 0.3; }
          40% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function Input({ onNewMessage, setTyping }) {
  const [text, setText] = useState("");
  const typingTimeoutRef = useRef(null);
  // When the last "typing" write went out; null once "stopped" has been sent,
  // so the next burst writes immediately again.
  const lastTypingWriteRef = useRef(null);
  // When the current message started being composed, and whether any of it was
  // pasted. Refs rather than state: they must not trigger a re-render on every
  // keystroke, and they are read only when the message is sent. Both reset
  // once the box is empty again, so they describe the message actually sent
  // rather than the whole time the participant sat on the stage.
  const composeStartedAtRef = useRef(null);
  const pastedRef = useRef(false);

  const resetComposition = () => {
    composeStartedAtRef.current = null;
    pastedRef.current = false;
  };

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    };
  }, []);

  const stopTyping = useCallback(() => {
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = null;
    lastTypingWriteRef.current = null;
    setTyping(false);
  }, [setTyping]);

  const handleTyping = useCallback(() => {
    const now = Date.now();
    if (
      lastTypingWriteRef.current === null ||
      now - lastTypingWriteRef.current >= TYPING_WRITE_INTERVAL_MS
    ) {
      lastTypingWriteRef.current = now;
      setTyping(true);
    }
    // Every keystroke pushes the "stopped" write back, throttled or not.
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(stopTyping, TYPING_STOP_MS);
  }, [setTyping, stopTyping]);

  const resize = (e) => {
    const target = e.target;
    target.style.height = "inherit";
    target.style.height = `${Math.min(target.scrollHeight, 200)}px`;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const txt = text.trim();
    if (txt === "") return;
    if (txt.length > 1024) {
      alert("Max message length is 1024");
      return;
    }
    onNewMessage(txt, {
      composeStartedAt: composeStartedAtRef.current,
      pasted: pastedRef.current,
    });
    setText("");
    resetComposition();
    // Clear typing state on send
    stopTyping();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      handleSubmit(e);
      resize(e);
    }
  };

  return (
    <form
      className="p-2 flex items-stretch gap-2 border-t"
      onSubmit={handleSubmit}
    >
      <textarea
        name="message"
        id="message"
        rows={1}
        className="peer resize-none bg-transparent block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-200 placeholder:text-gray-300 focus:ring-2 focus:ring-inset focus:ring-empirica-500 sm:text-sm sm:leading-6"
        placeholder="Say something"
        onKeyDown={handleKeyDown}
        onKeyUp={resize}
        onPaste={() => {
          pastedRef.current = true;
        }}
        value={text}
        onChange={(e) => {
          const value = e.target.value;
          if (value.trim()) {
            // First content of a new message: start the composition clock.
            if (composeStartedAtRef.current === null) {
              composeStartedAtRef.current = Date.now();
            }
            handleTyping();
          } else {
            // Emptied the box: whatever comes next is a fresh message.
            resetComposition();
          }
          setText(value);
        }}
      />
      <button
        type="button"
        className="rounded-md bg-gray-100 w-9 h-9 p-2 text-sm font-semibold text-gray-500 shadow-sm hover:bg-gray-200 hover:text-empirica-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-empirica-500"
        onClick={handleSubmit}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-full w-full fill-current"
          viewBox="0 0 512 512"
        >
          <path d="M498.1 5.6c10.1 7 15.4 19.1 13.5 31.2l-64 416c-1.5 9.7-7.4 18.2-16 23s-18.9 5.4-28 1.6L284 427.7l-68.5 74.1c-8.9 9.7-22.9 12.9-35.2 8.1S160 493.2 160 480V396.4c0-4 1.5-7.8 4.2-10.7L331.8 202.8c5.8-6.3 5.6-16-.4-22s-15.7-6.4-22-.7L106 360.8 17.7 316.6C7.1 311.3 .3 300.7 0 288.9s5.9-22.8 16.1-28.7l448-256c10.7-6.1 23.9-5.5 34 1.4z" />
        </svg>
      </button>
    </form>
  );
}

function Loading() {
  return (
    <div className="h-full w-full flex justify-center items-center">
      <div className="text-gray-400">Loading...</div>
    </div>
  );
}

/**
 * Returns a human-readable relative time string.
 * Shows 5-second increments for recent messages instead of all "now".
 */
function relTime(date) {
  const now = new Date();
  const difference = (now.getTime() - date.getTime()) / 1000;

  if (difference < 5) {
    return "now";
  } else if (difference < 60) {
    return `${Math.floor(difference / 5) * 5}s`;
  } else if (difference < 3600) {
    return `${Math.floor(difference / 60)}m`;
  } else if (difference < 86400) {
    return `${Math.floor(difference / 3600)}h`;
  } else {
    return `${Math.floor(difference / 86400)}d`;
  }
}
