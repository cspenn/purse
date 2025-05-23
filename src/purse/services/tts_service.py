import pyttsx3
import logging
import asyncio
from typing import Optional, List, Dict, Any, Callable # Added Callable for type hint if needed

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.engine: Optional[pyttsx3.Engine] = None
        self.is_speaking: bool = False
        self.current_spoken_text: Optional[str] = None
        self._run_and_wait_task: Optional[asyncio.Task] = None # To manage the asyncio task for runAndWait

        try:
            logger.debug("Initializing TTS engine (pyttsx3)...")
            self.engine = pyttsx3.init()
            if self.engine:
                # Connect engine events to callbacks
                self.engine.connect('finished-utterance', self._on_speech_finish_sync)
                self.engine.connect('error', self._on_speech_error_sync)
                # Note: 'started-utterance' could also be connected if needed:
                # self.engine.connect('started-utterance', self._on_speech_start_sync)
                logger.info("🟢 TTS engine initialized successfully.")
            else:
                # This case should ideally not happen if pyttsx3.init() itself doesn't raise an error
                # but returns None, though it typically raises RuntimeError on failure.
                logger.error("🛑 pyttsx3.init() returned None. TTS will be unavailable.")
        except RuntimeError as e: # pyttsx3.init() can raise RuntimeError
            logger.error(f"🛑 Failed to initialize TTS engine (pyttsx3): {e}. TTS will be unavailable.", exc_info=True)
            self.engine = None # Ensure engine is None if init fails
        except Exception as e: # Catch any other unexpected init errors
            logger.error(f"🛑 An unexpected error occurred during TTS engine initialization: {e}. TTS will be unavailable.", exc_info=True)
            self.engine = None


    # Synchronous callbacks called by pyttsx3 engine thread
    def _on_speech_finish_sync(self, name: str, completed: bool):
        """Callback executed by pyttsx3 when an utterance finishes."""
        logger.debug(f"TTS callback: finished-utterance (Name: {name}, Completed: {completed})")
        if completed:
            # These state changes should ideally be done in the main asyncio event loop
            # if they affect asyncio-managed state or trigger UI updates.
            # Using call_soon_threadsafe if TTSService methods are called from main loop.
            # For now, direct state change, assuming speak/stop methods manage concurrency.
            self.is_speaking = False
            self.current_spoken_text = None 
            # If there's an asyncio task running runAndWait, it should now complete.
            # No direct way to signal it from here other than state change.
        # If not completed (e.g. stop() was called), is_speaking is handled by stop()

    def _on_speech_error_sync(self, name: str, exception: Exception):
        """Callback executed by pyttsx3 on a speech error."""
        logger.error(f"🛑 TTS callback: error (Name: {name}, Exception: {exception})")
        self.is_speaking = False
        self.current_spoken_text = None
        # If an error occurs, the runAndWait task might also terminate or hang.
        # Additional cleanup or task cancellation might be needed if runAndWait task is robustly managed.

    # Optional: started-utterance callback
    # def _on_speech_start_sync(self, name: str):
    #     logger.debug(f"TTS callback: started-utterance (Name: {name})")
    #     self.is_speaking = True # Could also be set here


    async def speak(self, text: str, voice_id: Optional[str] = None, rate: Optional[int] = None, volume: Optional[float] = None) -> bool:
        if not self.engine:
            logger.warning("🟡 TTS engine not available. Cannot speak.")
            return False
        
        if self.is_speaking or (self._run_and_wait_task and not self._run_and_wait_task.done()):
            logger.warning("🟡 TTS engine is already speaking or processing. Call stop() first or wait.")
            return False

        try:
            if voice_id: self.engine.setProperty('voice', voice_id)
            if rate: self.engine.setProperty('rate', rate) 
            if volume is not None: # Volume can be 0.0, so check for None explicitly
                if 0.0 <= volume <= 1.0:
                    self.engine.setProperty('volume', volume)
                else:
                    logger.warning(f"TTS volume {volume} out of range [0.0, 1.0]. Not set.")
            
            self.current_spoken_text = text
            self.is_speaking = True # Set before starting the blocking task
            logger.info(f"TTS starting to speak: \"{text[:70].replace(chr(10), ' ')}...\"")
            
            self.engine.say(text)
            
            # runAndWait is blocking. Run in a separate thread managed by asyncio.
            # Store the task in case we need to check its status or attempt cancellation (though cancelling thread tasks is tricky).
            loop = asyncio.get_running_loop()
            self._run_and_wait_task = loop.create_task(asyncio.to_thread(self.engine.runAndWait))
            
            # Wait for the task to complete. This makes speak() effectively blocking until speech finishes or errors.
            # If non-blocking speak is desired (fire-and-forget), don't await here.
            # Callbacks will handle state changes.
            # The subtask says "Return True if speech was initiated (actual completion is async via callback)"
            # This implies speak() should return quickly. So, don't await here.
            # The _run_and_wait_task will run in the background.
            # Callbacks _on_speech_finish_sync and _on_speech_error_sync will update state.
            
            # If speak() is to return immediately:
            # asyncio.create_task(asyncio.to_thread(self.engine.runAndWait)) # Fire and forget background task
            # However, managing self.is_speaking becomes more critical.
            # Let's assume the callbacks are reliable for is_speaking state.
            # The current `is_speaking` is set to True here. Callbacks set to False.

            # If self.engine.runAndWait() itself can be interrupted by self.engine.stop(),
            # then self.is_speaking will be correctly set by stop() or callbacks.
            # The task _run_and_wait_task is mainly to offload the blocking call.
            
            # No await here: return True to indicate speech was queued.
            return True

        except Exception as e:
            logger.error(f"🛑 Error during TTS speak call for text '{text[:50]}...': {e}", exc_info=True)
            self.is_speaking = False # Ensure reset on error during setup
            self.current_spoken_text = None
            if self._run_and_wait_task and not self._run_and_wait_task.done():
                # Attempt to cancel if task was created but error occurred before it ran far
                # This is speculative, as to_thread tasks are not directly cancellable mid-execution.
                self._run_and_wait_task.cancel() 
            return False

    async def stop(self) -> None:
        if not self.engine:
            logger.debug("TTS engine not available. Nothing to stop.")
            return
        
        # Check is_speaking first. If pyttsx3 has a queue and isBusy(), that's more robust.
        # pyttsx3's engine.isBusy() might be useful but not standard across all backends.
        if self.is_speaking or (self._run_and_wait_task and not self._run_and_wait_task.done()):
            logger.info("TTS attempting to stop speech.")
            try:
                # engine.stop() should clear the command queue and stop current speech.
                # This call is synchronous.
                await asyncio.to_thread(self.engine.stop)
                # Some backends might need runAndWait to process the stop command fully.
                # This is tricky. If runAndWait is already running in its task, calling it again is problematic.
                # Typically, stop() is enough. The callback _on_speech_finish_sync should fire with completed=False.
            except Exception as e:
                logger.error(f"🛑 Error during TTS engine.stop(): {e}", exc_info=True)
            finally:
                # Ensure state is reset regardless of stop() success, as intent is to stop.
                self.is_speaking = False
                self.current_spoken_text = None
                if self._run_and_wait_task and not self._run_and_wait_task.done():
                    # If the runAndWait task is still around (e.g., stop() didn't make it exit quickly),
                    # cancelling it might be attempted, though direct cancellation of to_thread task is not effective.
                    # The task should complete once runAndWait finishes (due to stop or natural end).
                    logger.debug("TTS runAndWait task might still be finishing up after stop().")
        else:
            logger.debug("TTS not speaking or no active speech task. Nothing to stop.")


    def get_available_voices(self) -> List[Dict[str, Any]]:
        if not self.engine:
            logger.warning("🟡 TTS engine not available. Cannot get voices.")
            return []
        
        voices_data: List[Dict[str, Any]] = []
        try:
            voices = self.engine.getProperty('voices')
            for voice in voices:
                # Common attributes: id, name. Others might not be present on all platforms/engines.
                lang_list: List[str] = []
                # voice.languages is not a standard pyttsx3 attribute, handle potential AttributeError
                if hasattr(voice, 'languages') and isinstance(voice.languages, list):
                    lang_list = [str(lang) for lang in voice.languages] # Ensure strings

                voices_data.append({
                    'id': str(voice.id),
                    'name': str(getattr(voice, 'name', 'Unknown Name')),
                    'languages': lang_list,
                    'gender': str(getattr(voice, 'gender', 'Unknown Gender')),
                    'age': getattr(voice, 'age', None) # Age might be int or None
                })
            return voices_data
        except Exception as e:
            logger.error(f"🛑 Could not retrieve TTS voices: {e}", exc_info=True)
            return []

    def set_property(self, name: str, value: Any) -> None:
        if not self.engine:
            logger.warning(f"🟡 TTS engine not available. Cannot set property '{name}'.")
            return
        try:
            self.engine.setProperty(name, value)
            logger.debug(f"TTS property '{name}' set to '{value}'.")
        except Exception as e:
            logger.error(f"🛑 Error setting TTS property '{name}' to '{value}': {e}", exc_info=True)

    async def shutdown(self):
        """Cleanly stop any ongoing speech and prepare for app exit."""
        logger.info("Shutting down TTS service...")
        if self.is_speaking:
            await self.stop()
        # Wait for the run_and_wait_task to finish if it exists
        if self._run_and_wait_task and not self._run_and_wait_task.done():
            logger.debug("Waiting for TTS runAndWait task to complete during shutdown...")
            try:
                await asyncio.wait_for(self._run_and_wait_task, timeout=2.0) # Wait a bit
            except asyncio.TimeoutError:
                logger.warning("TTS runAndWait task did not complete within timeout during shutdown.")
            except Exception as e:
                logger.error(f"Error waiting for TTS task during shutdown: {e}")
        self.engine = None # Release engine reference
        logger.info("TTS service shutdown complete.")

```
