
import collections
import logging
import sys
import os
import imp
import weakref

from .plugin import Plugin, PluginBase, Configurable, NamedService, CLI
from .plugin import EventListener
from . import cjc_globals
from . import ui

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

    def __getitem__(self, index):
        for i, item in enumerate(self._generator()):
            if index == i:
                return item
        raise IndexError, index

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

def plugin_module_name(plugin_name):
    return "cjc._plugins." + plugin_name

class PluginContainer(object):
    """Plugin manager and a registry for the plugin-provided services.
    
    :Ivariables:
        - `_interface_cache`: mapping keeping services indexed by a class and name.
          Service lists are added here when first looked up.
        - `_configurables`: registry of known configurables, indexed by the namespaces
        - `_plugins`: registry of loaded Plugin objects. Keys are the module names, values
          are lists of Plugin-subclass instances.
        - `_plugin_dirs`: list of directories searched for plugins
        - `_warnings_emitted`: set of (service type, service name) pairs for
          which a 'service conflict' warnings were emitted by `get_service`."""

    def __init__(self, plugin_dirs):
        self._interface_cache = collections.defaultdict(WeakSequence)
        self._configurables = weakref.WeakValueDictionary()
        self._plugins = {}
        self._plugin_dirs = list(plugin_dirs)
        self._warnings_emitted = set()
        if "cjc._plugins" not in sys.modules:
            package = imp.new_module("cjc._plugins")
            package.__path__ = self._plugin_dirs
            package.__file__ = "<cjc plugins>"
            sys.modules["cjc._plugins"] = package

    def get_services(self, base_class, name = None):
        """Get all services subclassing given base class and, optionally,
        matching given name.

        :Raises: `KeyError` when no matching service is found
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
        matching given name.
        
        :Raises: `KeyError` when the service is not found
        """
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

    def _register_configurable(self, obj):
        """Register a `Configurable` service."""
        namespace = obj.settings_namespace
        if namespace in self._configurables:
            logger.error("Configuration namespace conflict: {0!r}"
                                                .format(namespace,))
        else:
            logger.debug("Registering a Configurable {0!r}"
                            " with namespace {1!r}".format(obj, namespace))
            self._configurables[namespace] = obj

    def _register_cli(self, obj):
        """Register a `CLI` service."""
        command_table = obj.get_command_table()
        command_table.install()
        ui.activate_cmdtable(obj.command_table_name, obj)

    def _register_event_listener(self, obj):
        """Register an `EventListener` service."""
        event_handlers = obj.get_event_handlers()
        cjc = cjc_globals.application
        for events, handler in event_handlers:
            for event in events:
                cjc.add_event_handler(event, handler)

    def _register(self, obj):
        """Register object as a plugin service."""
        logger.debug("Registering object: {0!r}".format(obj))
        if isinstance(obj, Configurable):
            self._register_configurable(obj)
        if isinstance(obj, CLI):
            self._register_cli(obj)
        if isinstance(obj, EventListener):
            self._register_event_listener(obj)
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
                if mod.__name__.startswith("cjc._plugins."):
                    mod_name = mod.__name__[13:]
                    plugin = plugin(cjc_globals.application, mod_name)
                else:
                    logger.warning("Unexpected module name: {0!r}".format(
                                                                 mod.__name__))
            else:
                plugin = plugin()
            for obj in plugin.services:
                objects.append(obj)
                self._register(obj)
        return objects

    def _load_plugin(self, name):
        """Load plugin by name.
        
        The plugin will be loaded as cjc._pugins.name"""
        try:
            full_name = plugin_module_name(name)
            logger.debug("Importing plugin {0!r}, module name: {1!r}"
                                                    .format(name, full_name))
            if full_name in sys.modules:
                logger.debug("Module was already in sys.path, reloading")
                mod = reload(sys.modules[full_name])
            else:
                __import__(full_name)
                mod = sys.modules[full_name]
                logger.debug("Module loaded: {0!r}".format(mod))
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
            mod = sys.modules[plugin_module_name(name)]
            mod = reload(mod)
            new_objects = self._load_plugin_from_module(mod)
        except:
            logger.exception("Exception:")
            logger.info("Plugin reload failed")
            del self.plugins[name]
        else:
            self.plugins[name] = new_objects

    def load_plugins(self):
        """Load all plugins from the plugin directories."""
        for directory in self._plugin_dirs:
            try:
                files = os.listdir(directory)
            except (OSError,IOError), err:
                logger.debug("Couldn't get plugin list: %s" % (err,))
                logger.info("Skipping plugin directory %s" % (directory,))
                continue
            logger.info("Loading plugins from %s:" % (directory, ))
            for filename in files:
                path = os.path.join(directory, filename)
                if os.path.isdir(path):
                    # a package?
                    name = filename
                    if (not os.path.exists(
                                        os.path.join(path, "__init__.py")) 
                            and not os.path.exists(
                                        os.path.join(path, "__init__.pyc"))):
                        continue
                elif not "." in filename:
                    continue
                else:
                    # a python script?
                    name, ext = filename.rsplit(".", 1)
                    if ext not in ("py", "pyc"):
                        continue
                if not self._plugins.has_key(name):
                    logger.info("  %s" % (name,))
                    self._load_plugin(name)
