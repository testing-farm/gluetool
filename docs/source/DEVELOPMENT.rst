Development
===========

Environment
-----------

Before moving on to the actual setup, there are few important notes:

-  **The only supported and (sort of tested) way of installation and using ``gluetool`` is a separate virtual
   environment!** It may be possible to install ``gluetool`` directly somewhere into your system but we don't
   recommend that, we don't use it that way, and we don't know what kind of hell you might run into. Please,
   stick with a ``virtualenv``.

   Since ``gluetool`` and its dependencies are managed and installed with `Poetry <https://python-poetry.org/>`_,
   it will create a ``virtualenv`` for you. So you don't need to worry about that, but it's good to know the basics
   about how a ``virtualenv`` works and what it's used for. If you don't have Poetry installed or if you have any
   specific requirements, please see the `Poetry documentation <https://python-poetry.org/docs/>`_.

-  The tested distributions (as in "we're using these") are either
   recent Fedora, RHEL or CentOS. You could try to install ``gluetool``
   in a different environment - or even development trees of Fedora, for
   example - please, make notes about differences, and it'd be awesome
   if your first merge request could update this file :)

Requirements
------------

To begin digging into ``gluetool`` sources, there are few requirements:

-  ``poetry``

-  ``ansible-playbook``

-  ``pre-commit``

Installation
------------

1. Clone ``gluetool`` repository - your working copy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    git clone github:<your username>/<your fork name>

2. Install ``gluetool``
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    cd gluetool
    poetry install

3. Enable pre-commit
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    pre-commit install

4. (optional) Activate Bash completion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Poetry's virtualenv can be found with:

.. code-block:: bash

    poetry env list --full-path

We can source the generated bash completion script at the end of the ``virtualenv`` activate script.

.. code-block:: bash

    gluetool --module-path gluetool_modules/ bash-completion > $VIRTUAL_ENV/bin/gluetool-bash-completition
    echo "source $VIRTUAL_ENV/bin/gluetool-bash-completition" >> $VIRTUAL_ENV/bin/activate

It will start working next time you activate your virtualenv via ``poetry shell``. To activate bash completion immediately, source the generated file.

5. Add configuration
~~~~~~~~~~~~~~~~~~~~~~

``gluetool`` looks for its configuration in a local directory (among others), in ``./.gluetool.d`` to be specific. Add
configuration for the modules according to your preference.

Now every time you activate your new virtualenv, you should be able to run ``gluetool``:

.. code-block:: bash

    gluetool -h
    usage: gluetool [opts] module1 [opts] [args] module2 ...

    optional arguments:
    ...

Test suites
-----------

The test suite is governed by ``tox`` and ``py.test``. Before running the test suite, you have to install ``tox``:

.. code-block:: bash

    pip install tox

Tox can be easily executed by:

.. code-block:: bash

    tox

Tox also accepts additional options which are then passed to ``py.test``:

.. code-block:: bash

    tox -- --cov=gluetool --cov-report=html:coverage-report

Tox creates (and caches) virtualenv for its test runs, and uses them for
running the tests. It integrates multiple different types of test (you
can see them by running ``tox -l``).

Documentation
-------------

Auto-generated documentation is located in ``docs/`` directory. To
update your local copy, run these commands:

.. code-block:: bash

    ansible-playbook ./generate-docs.yml

Then you can read generated docs by opening ``docs/build/html/index.html``.
