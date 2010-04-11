
import collections
import logging
import sys
import os
import weakref

from .plugin import Plugin, PluginBase, Configurable, NamedService
from . import cjc_globals

logger = logging.getLogger("cjc.plugins")

class WeakSequence(collections.Iterable):
    """Simple 'weak' container preserving item order."""
    def __init__(self, values = None):
        """
        :Parameters:
            - `values`: iterable with initial values
        """
        if values is None:
            self._values = []
        elif None in values:
            raise ValueError, "WeakSequence cannot store None"
        else:
            self._values = [ weakref.ref(val) for val in values ]

    def _generator(self):
        """Generator yielding contained items."""
        new_values = None
        for ref in self._values:
            value = ref()
            if value is None:
                if new_values is None:
                    new_values = self._values
                new_values.remove(ref)
            else:
                yield value
        if new_values:
            self._values = new_values

    def __iter__(self):
        """Return an iterator over contained items."""
        return self._generator()

    def __contains__(self, value):
        if value is None:
            return False
        return any(ref() is value for ref in self._values)

    def __len__(self):
        return sum(1 for ref in self._values if ref() is not None)
    
    def append(self, value):
        """Add an item at the end of the sequence."""
        if value is None:
            raise ValueError, "WeakSequence cannot store None"
        self._values.append(weakref.ref(value))

class PluginContainer(object):
    """Plugin manager and a registry for the plugin-provided services.
    
    :Ivariables:
        - `_interface_cache`: mapping keeping services indexed by a class and name.
          Service lists are added here when first looked up.
        - `_configurables`: registry of known configurables, indexed by the namespaces
        - `_plugins`: registry of loaded Plugin objects. Keys are the module names, values
          are lists of Plugin-subclass instances.
        - `_plugin_modules`: information of loaded plugin modules. Keys are the module names,
          values are tuples of module object and sys.path used to load it. These are used for reloading
          the modules when neccessary.
        - `_plugin_dirs`: list of directories searched for plugins
        - `_warnings_emitted`: set of (service type, service name) pairs for
          which a 'service conflict' warnings were emitted by `get_service`."""

    def __init__(self, plugin_dirs):
        self._interface_cache = collections.defaultdict(WeakSequence)
        self._configurables = weakref.WeakValueDictionary()
        self._plugins = {}
        self._plugin_modules = {}
        self._plugin_dirs = plugin_dirs
        self._warnings_emitted = set()

    def get_services(self, base_class, name = None):
        """Get all services subclassing given base class and, optionally,
        matching given name.

        :Return: all plugin inheriting from given ABC"""
        if not base_class in self._interface_cache:
            for objects in self._plugins.values():
                for obj in objects:
                    if not isinstance(obj, base_class):
                        continue
                    self._interface_cache[base_class].append(obj)
                    if isinstance(obj, NamedService):
                        self._interface_cache[base_class, obj.service_name] = obj
        if name is not None:
            return self._interface_cache[base_class, name]
        else:
            return self._interface_cache[base_class]

    def get_service(self, base_class, name = None):
        """Get a single service implementing given interface and, optionally,
        matching given name."""
        services = self.get_services(base_class, name)
        if not services:
            raise KeyError, (base_class, name)
        if len(services) > 1 and (base_class, name) not in self._warnigs_emitted:
            if name is not None:
                logger.warning(u"Multiple {0!r} services with name {1!r} found"
                                            .format(base_class.__name__, name))
            else:
                logger.warning(u"Multiple {0!r} found".format(name))
            self._warnigs_emitted.add((base_class, name))
        return services[0]

    def get_configurable(self, namespace):
        """Get a configurable object providing given namespace."""
        return self._configurables[namespace]
    
    def get_configurables(self):
        """Get all known configurables."""
        return self._configurables.values()

    @property
    def setting_namespaces(self):
        """All known setting namespaces."""
        return set(self._configurables.keys())

    def _register(self, obj):
        """Register object as a plugin service."""
        logger.debug("Registering object: {0!r}".format(obj))
        if isinstance(obj, Configurable):
            namespace = obj.settings_namespace
            if namespace in self._configurables:
                logger.error("Configuration namespace conflict: {0!r}"
                                                    .format(namespace,))
            else:
                logger.debug("Registering a Configurable {0!r}"
                                " with namespace {1!r}".format(namespace, obj))
                self._configurables[namespace] = obj
        for base_class in self._interface_cache:
            if isinstance(obj, base_class) \
                        and not obj in self._interface_cache[base_class]:
                self._interface_cache[base_class].append(obj)
                if isinstance(obj, NamedService):
                    self._interface_cache[base_class, obj.service_name] = obj

    def _load_plugin_from_module(self, mod):
        """Load `Plugin` object from a module object."""
        objects = []
        for attr in dir(mod):
            plugin = getattr(mod, attr)
            if not isinstance(plugin, type):
                # skip non-new-style-class objects
                continue
            if plugin.__module__ != mod.__name__:
                # skip imported objects
                continue
            if not issubclass(plugin, Plugin):
                # skip non-plugin classes
                continue
            if issubclass(plugin, PluginBase):
                plugin = plugin(cjc_globals.application, mod.__name__)
            else:
                plugin = plugin()
            for obj in plugin.services:
                objects.append(obj)
                self._register(obj)
            return objects

    def _load_plugin(self, name):
        """Load plugin by name from current `sys.path` or the path used
        recently for loading the plugin module."""
        try:
            if name in self._plugin_modules:
                mod, sys_path = self._plugin_modules.get(name)
                old_sys_path, sys.path = sys.path, sys_path
                try:
                    mod = reload(mod)
                finally:
                    sys.path = old_sys_path
            else:
                mod = __import__(name)
                sys_path = sys.path
            self._plugin_modules[name] = (mod, sys_path)
            self._plugins[name] = self._load_plugin_from_module(mod)
        except:
            logger.exception("Exception:")
            logger.info("Plugin load failed")

    def load_plugin(self, name):
        """Load a plugin by name, looking it up in the plugin directories."""
        sys_path = sys.path
        try:
            for path in self._plugin_dirs:
                sys.path = [path] + sys_path
                for suffix in (".py", ".pyc", ".pyo"):
                    filename = os.path.join(path, name + ".py")
                    if os.path.exists(filename):
                        break
                    filename = None
                if not filename:
                    continue
                if self.plugins.has_key(name):
                    logger.error("Plugin %s already loaded!" % (name,))
                    return
                logger.info("Loading plugin %s..." % (name,))
                self._load_plugin(name)
                return
            logger.error("Couldn't find plugin %s" % (name,))
        finally:
            sys.path = sys_path

    def unload_plugin(self, name):
        """Unload a previously loaded plugin.
        
        Warning: plugin configuration is lost."""
        plugin = self.plugins.get(name, None)
        if plugin is None:
            logger.error("Plugin %s is not loaded" % (name, ))
            return False
        logger.info("Unloading plugin %s..." % (name, ))
        for obj in plugin:
            try:
                r = obj.unload()
            except:
                logger.exception("Exception:")
                r = None
                break
        if not r:
            logger.error("Plugin %s cannot be unloaded" % (name,))
            return False
        del self._plugins[name]
        return True

    def reload_plugin(self, name):
        """Reload a previously loaded plugin."""
        plugin = self.plugins.get(name, None)
        if plugin is None:
            logger.error("Plugin %s is not loaded" % (name,))
            return False
        logger.info("Reloading plugin %s..." % (name,))
        for obj in plugin:
            try:
                r = obj.unload()
            except:
                logger.exception("Exception:")
                r = None
                break
        if not r:
            logger.error("Plugin %s cannot be reloaded" % (name,))
            return False
        try:
            mod, sys_path = self._plugin_modules[name]
            old_sys_path, sys.path = sys.path, sys_path
            try:
                mod = reload(mod)
            finally:
                sys.path = old_sys_path
            self.plugin_modules[name] = (mod, sys_path)
            new_objects = self._load_plugin_from_module(mod)
        except:
            logger.exception("Exception:")
            logger.info("Plugin reload failed")
            del self.plugins[name]
        else:
            self.plugins[name] = new_objects

    def load_plugins(self):
        """Load all plugins from the plugin directories."""
        sys_path = sys.path
        try:
            for path in self._plugin_dirs:
                sys.path = [path] + sys_path
                try:
                    files = os.listdir(path)
                except (OSError,IOError), err:
                    logger.debug("Couldn't get plugin list: %s" % (err,))
                    logger.info("Skipping plugin directory %s" % (path,))
                    continue
                logger.info("Loading plugins from %s:" % (path, ))
                for filename in files:
                    if not "." in filename:
                        continue
                    name, ext = filename.rsplit(".", 1)
                    if ext not in ("py", "pyc", "pyo"):
                        continue
                    if not self._plugins.has_key(name):
                        logger.info("  %s" % (name,))
                        self._load_plugin(name)
        finally:
            sys.path = sys_path
