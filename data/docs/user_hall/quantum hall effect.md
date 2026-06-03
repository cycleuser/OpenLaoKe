## Quantum Hall Effects

Mark O. Goerbig Laboratoire de Physique des Solides, CNRS UMR 8502 Universit´e Paris-Sud, France

October 21, 2009

#### Preface

The present notes cover a series of three lectures on the quantum Hall effect given at the Singapore session "Ultracold Gases and Quantum Information" at Les Houches Summer School 2009. Almost 30 years after the discovery of the quantum Hall effect, the research subject of quantum Hall physics has definitely acquired a high degree of maturity that is reflected by a certain number of excellent reviews and books, of which we can cite only a few \[1, 2, [3\]](#page-114-2) for possible further or complementary reading. Also the different sessions of Les Houches Summer School have covered in several aspects quantum Hall physics, and S. M. Girvin's series of lectures in 1998 [\[4\]](#page-114-3) have certainly become a reference in the field.1 Girvin's lecture notes were indeed extremely useful for myself when I started to study the quantum Hall effect at the beginning of my Master and PhD studies.

The present lecture notes are complementary to the existing literature in several aspects. One should first mention its introductory character to the field, which is in no way exhaustive. As a consequence, the presentation of one-particle physics and a detailed discussion of the integer quantum Hall effect occupy the major part of these lecture notes, whereas the – certainly more interesting – fractional quantum Hall effect, with its relation to strongly-correlated electrons, its fractionally charged quasi-particles and fractional statistics, is only briefly introduced.

Furthermore, we have tried to avoid as much as possible the formal aspects of the fractional quantum Hall effect, which is discussed only in the framework of trial wave functions `a la Laughlin. We have thus omitted, e.g., a presentation of Chern-Simons theories and related quantum-field theoretical approaches, such as the Hamiltonian theory of the fractional quantum Hall effect [\[5\]](#page-114-4), as much as the relation between the quantum Hall effect and conformal field theories. Although these theories are extremely fruitful and still promising for a deeper understanding of quantum Hall physics, a detailed discussion of them would require more space than these lecture notes with their introductory character can provide.

Another complementary aspect of the present lecture notes as compared to existing textbooks consists of an introduction to Landau-level quantisation that treats in a parallel manner the usual non-relativistic electrons in semiconductor heterostructures and relativistic electrons in graphene (two-dimensional graphite). Indeed, the 2005 discovery of a quantum Hall effect in this amazing material \[6, [7\]](#page-114-6) has given a novel and unexpected boost to research in quantum Hall physics.

As compared to the (oral) lectures, the present notes contain slightly more information. An example is Laughlin's plasma analogy, which is described in Sec. 4.2.5, although it was not discussed in the oral lectures. Furthermore, I have decided to add a chapter on multi-component quantum Hall systems, which, for completeness, needed to be at least briefly discussed.

<span id="page-1-0"></span><sup>1</sup>These lectures are also available on the preprint server, <http://arxiv.org/abs/cond-mat/9907002>

Before the Singapore session of Les Houches Summer School, this series of lectures had been presented in a similar format at the (French) Summer School of the Research Grouping "Physique M´esoscopique" at the Institute of Scientific Research, Carg`ese, Corsica, in 2008. Furthermore, a longer series of lectures on the quantum Hall effect was prepared in collaboration with my colleague and former PhD advisor Pascal Lederer (Orsay, 2006). Its aim was somewhat different, with an introduction to the Hamiltonian theories of the fractional quantum Hall effect and correlation effects in multi-component systems. As already mentioned above, the latter aspect is only briefly introduced within the present lecture notes and a discussion of Hamiltonian theories is completely absent. The Orsay series of lectures was repeated by Pascal Lederer at the Ecole Polytechnique F´ed´erale in Lausanne Switzerland, in 2006, and at the University of Recife, Brazil, in 2007. The finalisation of these longer and more detailed lecture notes (in French) is currently in progress. The graphene-related aspects of the quantum Hall effect have furthermore been presented in a series of lectures on graphene (Orsay, 2008) prepared in collaboration with Jean-No¨el Fuchs, whom I would like to thank for a careful reading of the present notes.

# Contents

| 1 |     | Introduction |                                                            | 7  |
|---|-----|--------------|------------------------------------------------------------|----|
|   | 1.1 |              | History of the (Quantum) Hall Effect                       | 7  |
|   |     | 1.1.1        | The physical system<br>                                    | 7  |
|   |     | 1.1.2        | Classical Hall effect<br>                                  | 8  |
|   |     | 1.1.3        | Shubnikov-de Haas effect<br>                               | 11 |
|   |     | 1.1.4        | Integer quantum Hall effect<br>                            | 13 |
|   |     | 1.1.5        | Fractional quantum Hall effect<br>                         | 14 |
|   |     | 1.1.6        | Relativistic quantum Hall effect in graphene               | 15 |
|   | 1.2 |              | Two-Dimensional Electron Systems                           | 16 |
|   |     | 1.2.1        | Field-effect transistors                                   | 16 |
|   |     | 1.2.2        | Semiconductor heterostructures                             | 18 |
|   |     | 1.2.3        | Graphene<br>                                               | 19 |
| 2 |     |              | Landau Quantisation                                        | 21 |
|   | 2.1 |              | Basic One-Particle Hamiltonians for B = 0<br>              | 21 |
|   |     | 2.1.1        | Hamiltonian of a free particle                             | 21 |
|   |     | 2.1.2        | Dirac Hamiltonian in graphene<br>                          | 23 |
|   | 2.2 |              | Hamiltonians for Non-Zero B Fields<br>                     | 26 |
|   |     | 2.2.1        | Minimal coupling and Peierls substitution                  | 26 |
|   |     | 2.2.2        | Quantum mechanical treatment                               | 27 |
|   | 2.3 |              | Landau Levels<br>                                          | 29 |
|   |     | 2.3.1        | Non-relativistic Landau levels                             | 29 |
|   |     | 2.3.2        | Relativistic Landau levels<br>                             | 30 |
|   |     | 2.3.3        | Level degeneracy                                           | 34 |
|   |     | 2.3.4        | Semi-classical interpretation of the level degeneracy<br>  | 36 |
|   | 2.4 | Eigenstates  |                                                            | 39 |
|   |     | 2.4.1        | Wave functions in the symmetric gauge<br>                  | 39 |
|   |     | 2.4.2        | Wave functions in the Landau gauge                         | 41 |
| 3 |     |              | Integer Quantum Hall Effect                                | 43 |
|   | 3.1 |              | Electronic Motion in an External Electrostatic Potential   | 45 |
|   |     | 3.1.1        | Semi-classical treatment                                   | 45 |
|   |     | 3.1.2        | Electrostatic potential with translation invariance in the |    |
|   |     |              | x-direction<br>                                            | 47 |

|   | 3.2 |       | Conductance of a Single Landau Level                       | 48  |
|---|-----|-------|------------------------------------------------------------|-----|
|   |     | 3.2.1 | Edge states<br>                                            | 50  |
|   | 3.3 |       | Two-terminal versus Six-Terminal Measurement               | 51  |
|   |     | 3.3.1 | Two-terminal measurement<br>                               | 51  |
|   |     | 3.3.2 | Six-terminal measurement                                   | 52  |
|   | 3.4 |       | The Integer Quantum Hall Effect and Percolation            | 54  |
|   |     | 3.4.1 | Extended and localised bulk states in an optical measure   |     |
|   |     |       | ment                                                       | 57  |
|   |     | 3.4.2 | Plateau transitions and scaling laws<br>                   | 58  |
|   | 3.5 |       | Relativistic Quantum Hall Effect in Graphene               | 60  |
| 4 |     |       | Strong Correlations and the Fractional Quantum Hall Effect | 65  |
|   | 4.1 |       | The Role of Coulomb Interactions<br>                       | 66  |
|   | 4.2 |       | Laughlin's Theory<br>                                      | 68  |
|   |     | 4.2.1 | Laughlin's guess from two-particle wave functions          | 68  |
|   |     | 4.2.2 | Haldane's pseudopotentials<br>                             | 71  |
|   |     | 4.2.3 | Quasi-particles and quasi-holes with fractional charge<br> | 74  |
|   |     | 4.2.4 | Experimental observation of fractionally charged quasi     |     |
|   |     |       | particles                                                  | 77  |
|   |     | 4.2.5 | Laughlin's plasma analogy                                  | 78  |
|   | 4.3 |       | Fractional Statistics<br>                                  | 80  |
|   |     | 4.3.1 | Bosons, fermions and anyons – an introduction<br>          | 80  |
|   |     | 4.3.2 | Statistical properties of Laughlin quasi-particles<br>     | 82  |
|   | 4.4 |       | Generalisations of Laughlin's Wave Function<br>            | 83  |
|   |     | 4.4.1 | Composite Fermions<br>                                     | 84  |
|   |     | 4.4.2 | Half-filled LLs and Pfaffian states                        | 87  |
| 5 |     |       | Brief Overview of Multicomponent Quantum-Hall Systems      | 89  |
|   | 5.1 |       | The Different Multi-Component Systems                      | 89  |
|   |     | 5.1.1 | The role of the electronic spin                            | 89  |
|   |     | 5.1.2 | Graphene as a four-component quantum Hall system           | 90  |
|   |     | 5.1.3 | Bilayer quantum Hall systems                               | 90  |
|   |     | 5.1.4 | Wide quantum wells<br>                                     | 92  |
|   | 5.2 |       | The State at ν = 1                                         | 92  |
|   |     | 5.2.1 | Quantum Hall ferromagnetism<br>                            | 93  |
|   |     | 5.2.2 | Exciton condensate in bilayer systems<br>                  | 95  |
|   |     | 5.2.3 | SU(4) ferromagnetism in graphene<br>                       | 98  |
|   | 5.3 |       | Multi-Component Wave Functions<br>                         | 99  |
|   |     | 5.3.1 | Halperin's wave function                                   | 99  |
|   |     | 5.3.2 | Generalised Halperin wave functions<br>102                 |     |
| A |     |       | Electronic Band Structure of Graphene                      | 105 |
| B |     |       | Landau Levels of Massive Dirac Particles                   | 111 |

# <span id="page-6-0"></span>Chapter 1

# Introduction

Quantum Hall physics – the study of two-dimensional (2D) electrons in a strong perpendicular magnetic field see Fig. [1.1\(a)] – has become an extremely important research subject during the last two and a half decades. The interest for quantum Hall physics stems from its position at the borderline between lowdimensional quantum systems and systems with strong electronic correlations, probably the major issues of modern condensed-matter physics. From a theoretical point of view, the study of quantum Hall systems required the elaboration of novel concepts some of which were better known in quantum-field theories used in high-energy rather than in condensed-matter physics, such e.g. charge fractionalisation, non-commutative geometries and topological field theories.

The motivation of the present lecture notes is to provide in an accessible manner the basic knowledge of quantum Hall physics and to enable thus interested graduate students to pursue on her or his own further studies in this subject. We have therefore tried, whereever we feel that a more detailed discussion of some aspects in this large field of physics would go beyond the introductory character of these notes, to provide references to detailed and pedagogical references or complementary textbooks.

## <span id="page-6-1"></span>1.1 History of the (Quantum) Hall Effect

#### <span id="page-6-2"></span>1.1.1 The physical system

Our main knowledge of quantum Hall systems, i.e. a system of 2D electrons in a perpendicular magnetic field, stems from electronic transport measurements, where one drives a current I through the sample and where one measures both the longitudinal and the transverse resistance (also called Hall resistance). The difference between these two resistances is essential and may be defined topologically: consider a current that is driven through the sample via two arbitrary contacts C1 and C4 in Fig. [1.1\(a)] and draw (in your mind) a line between these two contacts. A longitudinal resistance is a resistance measured between two (other) contacts that may be connected by a line that does not cross the

![](images/_page_7_Figure_1.jpeg)

<span id="page-7-1"></span>Figure 1.1: (a) 2D electrons in a perpendicular magnetic field (quantum Hall system). In a typical transport measurement, a current I is driven through the system via the contacts C1 and C4. The longitudinal resistance may be measured between the contacts C5 and C6 (or alternatively between C2 and C3). The transverse (or Hall) resistance is measured, e.g., between the contacts C3 and C5. (b) Classical Hall resistance as a function of the magnetic field.

line connecting C1 and C4. In Fig. 1.1(a), we have chosen the contacts C5 and C6 for a possible longitudinal resistance measurement. The transverse resistance is measured between two contacts that are connected by an imaginary line that necessarily crosses the line connecting C1 and C4 [e.g. C3 and C5 in Fig. 1.1(b)].

#### <span id="page-7-0"></span>1.1.2 Classical Hall effect

Evidently, if there is a quantum Hall effect, it is most natural to expect that there exists also a classical Hall effect. This is indeed the case, and its history goes back to 1879 when Hall showed that the transverse resistance  $R_H$  of a thin metallic plate varies linearly with the strength B of the perpendicular magnetic field [Fig. 1.1(b)],

$$R_H = \frac{B}{qn_{el}} , \qquad (1.1)$$

where q is the carrier charge (q = -e for electrons in terms of the elementary charge e that we define positive in the remainder of these lectures) and  $n_{el}$  is the 2D carrier density. Intuitively, one may understand the effect as due to the Lorentz force, which bends the trajectory of a charged particle such that a density gradient is built up between the two opposite sample sides that are separated by the contacts C1 and C4. Notice that the classical Hall resistance is still used today to determine, in material science, the carrier charge and density of a conducting material.

More quantitatively, the classical Hall effect may be understood within the Drude model for diffusive transport in a metal. Within this model, one considers

independent charge carriers of momentum p described by the equation of motion

$$\frac{d\mathbf{p}}{dt} = -e\left(\mathbf{E} + \frac{\mathbf{p}}{m_b} \times \mathbf{B}\right) - \frac{\mathbf{p}}{\tau},$$

where E and B are the electric and magnetic fields, respectively. Here, we consider transport of negatively charged particles (i.e. electrons with q = −e) with band mass mb. The last term takes into account relaxation processes due to the diffusion of electrons by generic impurities, with a characteristic relaxation time τ. The macroscopic transport characteristics, i.e. the resistivity or conductivity of the system, are obtained from the static solution of the equation of motion, dp/dt = 0, and one finds for 2D electrons with p = (px, py)

$$\begin{split} eE_x &= -\frac{eB}{m_b}p_y - \frac{p_x}{\tau}, \\ eE_y &= \frac{eB}{m_b}p_x - \frac{p_y}{\tau} \;, \end{split}$$

where we have chosen the magnetic field in the z-direction. In the above expressions, one notices the appearence of a characteristic frequency,

<span id="page-8-2"></span>
$$\omega_C = \frac{eB}{m_b} \,, \tag{1.2}$$

which is called cyclotron frequency because it characterises the cyclotron motion of a charged particle in a magnetic field. With the help of the Drude conductivity,

$$\sigma_0 = \frac{n_{el}e^2\tau}{m_b} \,, \tag{1.3}$$

one may rewrite the above equations as

$$\begin{split} \sigma_0 E_x &= -e n_{el} \frac{p_x}{m_b} - e n_{el} \frac{p_y}{m_b} (\omega_C \tau), \\ \sigma_0 E_y &= e n_{el} \frac{p_x}{m_b} (\omega_C \tau) - e n_{el} \frac{p_y}{m_b}, \end{split}$$

or, in terms of the current density

$$\mathbf{j} = -en_{el} \frac{\mathbf{p}}{m_b} , \qquad (1.4)$$

in matrix form as E = ρ j, with the resistivity tensor

<span id="page-8-0"></span>
$$\rho = \sigma^{-1} = \frac{1}{\sigma_0} \begin{pmatrix} 1 & \omega_C \tau \\ -\omega_C \tau & 1 \end{pmatrix} = \frac{1}{\sigma_0} \begin{pmatrix} 1 & \mu B \\ -\mu B & 1 \end{pmatrix}, \tag{1.5}$$

where we have introduced, in the last step, the mobility

<span id="page-8-1"></span>
$$\mu = \frac{e\tau}{m_b} \,. \tag{1.6}$$

From the above expression, one may immediately read off the Hall resistivity (the off-diagonal terms of the resistivity tensor  $\rho$ )

<span id="page-9-0"></span>
$$\rho_H = \frac{\omega_C \tau}{\sigma_0} = \frac{eB}{m_b} \tau \times \frac{m_b}{n_{el} e^2 \tau} = \frac{B}{e n_{el}} \ . \tag{1.7}$$

Furthermore, the conductivity tensor is obtained from the resistivity (1.5), by matrix inversion.

$$\sigma = \rho^{-1} = \begin{pmatrix} \sigma_L & -\sigma_H \\ \sigma_H & \sigma_L \end{pmatrix}, \tag{1.8}$$

with  $\sigma_L = \sigma_0/(1 + \omega_C^2 \tau^2)$  and  $\sigma_H = \sigma_0 \omega_C \tau/(1 + \omega_C^2 \tau^2)$ . It is instructive to discuss, based on these expressions, the theoretical limit of vanishing impurities, i.e. the limit  $\omega_C \tau \to \infty$  of very long scattering times. In this case the resistivity and conductivity tensors read

<span id="page-9-1"></span>
$$\rho = \begin{pmatrix} 0 & \frac{B}{en_{el}} \\ -\frac{B}{en_{el}} & 0 \end{pmatrix} \quad \text{and} \quad \sigma = \begin{pmatrix} 0 & -\frac{en_{el}}{B} \\ \frac{en_{el}}{B} & 0 \end{pmatrix}, \quad (1.9)$$

respectively. Notice that if we had put under the carpet the matrix character of the conductivity and resistivity and if we had only considered the longitudinal components, we would have come to the counter-intuitive conclusion that the (longitudinal) resistivity would vanish at the same time as the (longitudinal) conductivity. The transport properties in the clean limit  $\omega_C \tau \to \infty$  are therefore entirely governed, in the presence of a magnetic field, by the off-diagonal, i.e. transverse, components of the conductivity/resistivity. We will come back to this particular feature of quantum Hall systems when discussing the integer quantum Hall effect below.

#### Resistivity and resistance

The above treatment of electronic transport in the framework of the Drude model allowed us to calculate the conductivity or resistivity of classical diffusive 2D electrons in a magnetic field. However, an experimentalist does not measure a conductivity or resistivity, i.e. quantities that are easier to calculate for a theoretician, but a conductance or a resistance. Usually, these quantities are related to one another but depend on the geometry of the conductor – the resistance R is thus related to the resistivity  $\rho$  by  $R = (L/A)\rho$ , where L is the length of the conductor and A its cross section. From the scaling point of view of a d-dimensional conductor, the cross section scales as  $L^{d-1}$ , such that the scaling relation between the resistance and the resistivity is

$$R \sim \rho L^{2-d},\tag{1.10}$$

and one immediately notices that a 2D conductor is a special case. From the dimensional point of view, resistance and resistivity are the same in 2D, and the resistance is scale-invariant. Naturally, this scaling argument neglects the fact that the length L and the width W (the 2D cross section) do not necessarily

![](images/_page_10_Figure_2.jpeg)

<span id="page-10-1"></span>Figure 1.2: (a) Sketch of the Shubnikov-de Haas effect. Above a critical field Bc, the longitudinal resistance (grey) starts to oscillate as a function of the magnetic field. The Hall resistance remains linear in B. (b) Density of states (DOS). In a clean system, the DOS consists of equidistant delta peaks (grey) at the energies ǫ<sup>n</sup> = ¯hωC(n + 1/2), whereas in a sample with a stronger impurity concentration, the peaks are broadened (dashed lines). The continuous black line represents the sum of overlapping peaks, and E<sup>F</sup> denotes the Fermi energy.

coincide: indeed, the resistance of a 2D conductor depends in general on the so-called aspect ratio L/W via some factor f(L/W) [\[8\]](#page-114-7). However, in the case of the transverse Hall resistance it is the length of the conductor itself that plays the role of the cross section, such that the Hall resistivity and the Hall resistance truely coincide, i.e. f = 1. We will see in Chap. 3 that this conclusion also holds in the case of the quantum Hall effect and not only in the classical regime. Moreover, the quantum Hall effect is highly insensitive to the particular geometric properties of the sample used in the transport measurement, such that the quantisation of the Hall resistance is surprisingly precise (on the order of 10<sup>−</sup><sup>9</sup> ) and the quantum Hall effect is used nowadays in the definition of the resistance standard.

#### <span id="page-10-0"></span>1.1.3 Shubnikov-de Haas effect

A first indication for the relevance of quantum phenomena in transport measurements of 2D electrons in a strong magnetic field was found in 1930 with the discovery of the Shubnikov-de Haas effect [\[9\]](#page-114-8). Whereas the classical result \(1.5\) for the resistivity tensor stipulates that the longitudinal resistivity ρ<sup>L</sup> = 1/σ<sup>0</sup> (and thus the longitudinal resistance) is independent of the magnetic field, Shubnikov and de Haas found that above some characteristic magnetic field the longitudinal resistance oscillates as a function of the magnetic field. This is schematically depicted in Fig. 1.2\(a). In contrast to this oscillation in the longitudinal resistance, the Hall resistance remains linear in the B field, in agreement with the classical result from the Drude model \(1.7\).

The Shubnikov-de Haas effect is a consequence of the energy quantisation of

12 Introduction

the 2D electron in a strong magnetic field, as it has been shown by Landau at roughly the same moment. This so-called Landau quantisation will be presented in great detail in Sec. 2. In a nutshell, Landau quantisation consists of the quantisation of the cyclotron radius, i.e. the radius of the circular trajectory of an electron in a magnetic field. As a consequence this leads to the quantisation of its kinetic energy into so-called Landau levels (LLs),  $\epsilon_n = \hbar \omega_C (n+1/2)$ , where n is an integer. In order for this quantisation to be relevant, the magnetic field must be so strong that the electron performs at least one complete circular period without any collision, i.e.  $\omega_C \tau > 1$ . This condition defines the critical magnetic field  $B_c \simeq m_b/e\tau = \mu^{-1}$  above which the longitudinal resistance starts to oscillate, in terms of the mobility (1.6). Notice that today's samples of highest mobility are characterised by  $\mu \sim 10^7$  cm<sup>2</sup>/Vs =  $10^3$  m<sup>2</sup>/Vs such that one may obtain Shubnikov-de Haas oscillations at magnetic fields as low as  $B_c \sim 1$  mT.

The effect may be understood within a slightly more accurate theoretical description of electronic transport (e.g. with the help of the Boltzmann transport equation) than the Drude model. The resulting Einstein relation relates then the conductivity to a diffusion equation, and the longitudinal conductivity

<span id="page-11-2"></span>
$$\sigma_L = e^2 D\rho(E_F) \tag{1.11}$$

turns out to be proportional to the density of states (DOS)  $\rho(E_F)$  at the Fermi energy  $E_F$  rather than the electronic density, Due to Landau quantisation, the DOS of a clean system consists of a sequence of delta peaks at the energies  $\epsilon_n = \hbar \omega_C (n + 1/2)$ ,

$$\rho(\epsilon) = \sum_{n} g_n \delta(\epsilon - \epsilon_n),$$

where  $g_n$  is takes into account the degeneracy of the energy levels. These peaks are eventually impurity-broadened in real samples and may even overlap [see Fig. 1.2(b)], such that the DOS oscillates in energy with maxima at the positions of the energy levels  $\epsilon_n$ . Consider a fixed number of electrons in the sample that fixes the zero-field Fermi energy the B-field dependence of which we omit in the argument.<sup>2</sup> When sweeping the magnetic field, one varies the energy distance between the LLs, and the DOS thus becomes maximal when  $E_F$  coincides with the energy of a LL and minimal if  $E_F$  lies between two adjacent LLs. The resulting oscillation in the DOS as a function of the magnetic field translates via the relation (1.11) into an oscillation of the longitudinal conductivity (or resistivity), which is the essence of the Shubnikov-de Haas effect.

$$\int_{0}^{E_F} d\epsilon \, \rho(\epsilon, B) = n_{el}.$$

However, the basic features of the Shubnikov-de Haas oscillation may be understood when keeping the Fermi energy constant.

<span id="page-11-0"></span> $<sup>^{1}</sup>$ Notice, however, that the Fermi energy and thus the DOS is a function of the electronic density. Furthermore we mention that in a fully consistent treatment also the diffusion constant D depends on the density of states and eventually the magnetic field. This affects the precise form of the oscillation but not its periodicity.

<span id="page-11-1"></span><sup>&</sup>lt;sup>2</sup>Naturally, this is a crude assumption because if the density of states  $\rho(\epsilon, B)$  depends on the magnetic field, so does the Fermi energy via the relation

0.5

<span id="page-12-0"></span>1.1.4

1.0

0.5

0.0

16

![](images/_page_12_Picture_2.jpeg)

3/4

magnetic field B[T]

<span id="page-12-1"></span>Figure 1.3: Typical signature of the quantum Hall effect (measured by J. Smet, MPI-Stuttgart). Each plateau in the Hall resistance is accompanied by a vanishing longitudinal resistance. The classical Hall resistance is indicated by the dashed-dotted line. The numbers label the plateaus: integral n denote the IQHE

An even more striking manifestation of quantum mechanics in the transport properties of 2D electrons in a strong magnetic field was revealed 50 years later with the discovery of the integer quantum Hall effect (IQHE) by v. Klitzing, Dorda, and Pepper in 1980 [10]. The Nobel Prize was attributed in 1985 to v.

Indeed, the discovery of the IQHE was intimitely related to technological advances in material science, namely in the fabrication of high-quality field-effect transistors for the realisation of 2D electron gases. These technological

The IQHE occurs at low temperatures, when the energy scale set by the temperature  $k_BT$  is significantly smaller than the LL spacing  $\hbar\omega_C$ . It consists of a quantisation of the Hall resistance, which is no longer linear in B, as one would expect from the classical treatment presented above, but reveals plateaus at particular values of the magnetic field (see Fig. 1.3). In the plateaus, the

and n = p/q, with integral p and q, indicate the FQHE.

Integer quantum Hall effect

aspects will be briefly reviewed in separate a section (Sec. 1.2).

Klitzing for this extremely important discovery.

![](images/_page_13_Picture_0.jpeg)

<sup>2</sup>/h, and one observes

<span id="page-13-1"></span>R<sup>H</sup> =

 h e 2 1 n

14 Introduction Hall resistance is given in terms of universal constants – it is indeed a fraction of the inverse quantum of conductance e in terms of an integer n. The plateau in the Hall resistance is accompanied by a vanishing longitudinal resistance. This is at first sight reminiscent of the Shubnikov-de Haas effect, where the longitudinal resistance also reveals minima

resistance standard,3

the Shubnikov-de Haas regime to the IQHE. quantisation (typically <sup>∼</sup> <sup>10</sup><sup>−</sup><sup>9</sup>

which is also called the Klitzing constant \[11, [12\]](#page-114-11). Furthermore, as already mentioned in Sec. 1.1.2, the vanishing of the longitudinal resistance indicates

that the scattering time tends to infinity see Eq. [\(1.9\)] in the IQHE. This is another indication of the above-mentioned universality of the effect, i.e. that IQHE does not depend on a particular impurity (or scatterer) arrangement. A detailed presentation of the IQHE, namely the role of impurities, may be found in Chap. 3. 1.1.5 Fractional quantum Hall effect Three years after the discovery of the IQHE, an even more unexpected effect

Hall-resistance quantisation was discovered by Tsui, St¨ormer and Gossard with n = 1/3 [\[13\]](#page-114-12). From the phenomenological point of view, the effect is extremely reminiscent of the IQHE: whereas the Hall resistance is quantised and reveals a plateau, the longitudinal resistance vanishes (see Fig. 1.3, where different instances of both the IQHE and the FQHE are shown). However, the origins of the two effects are completely different: whereas the IQHE may be understood

resistance is defined by the IQHE.

although it never vanished. The vanishing of the longitudinal resistance at the Shubnikov-de Haas minima may indeed be used to determine the crossover from It is noteworth to mention that the quantisation of the Hall resistance \(1.12\) is a universal phenomenon, i.e. independent of the particular properties of the sample, such as its geometry, the host materials used to fabricate the 2D electron gas and, even more importantly, its impurity concentration or distribution. This universality is the reason for the enormous precision of the Hall-resistance ), which is nowadays – since 1990 – used as the

, (1.12)

<span id="page-13-3"></span>RK−<sup>90</sup> = h/e<sup>2</sup> = 25 812.807 Ω, (1.13)

<span id="page-13-0"></span>was observed in a 2D electron system of higher quality, i.e. higher mobility: the fractional quantum Hall effect (FQHE). The effect ows its name to the fact that contrary to the IQHE, where the number n in Eq. \(1.12\) is an integer, a

<span id="page-13-2"></span>from Landau quantisation, i.e. the kinetic-energy quantisation of independent electrons in a magnetic field, the FQHE is due to strong electronic correlations, when a LL is only partially filled and the Coulomb interaction between the <sup>3</sup>The subscript K honours v. Klitzing and 90 stands for the date since which the unit of

![](images/_page_14_Picture_0.jpeg)

Finally, we would mention in this brief (and naturally incomplete) historical overview a FQHE with n = 4/11 discovered in 2003 by Pan et al. [20]: it does not fit into the above-mentioned CF series, but it would correspond to a FQHE

Relativistic quantum Hall effect in graphene

Recently, quantum Hall physics experienced another unexpected boost with the discovery of a "relativistic" quantum Hall effect in graphene, a one-atom-thick layer of graphite [6, 7]. Electrons in graphene behave as if they were relativistic massless particles. Formally, their quantum-mechanical behaviour is no longer described in terms of a (non-relativistic) Schrödinger equation, but rather by a relativistic 2D Dirac equation [21]. As a consequence, Landau quantisation of the electrons' kinetic energy turns out to be different in graphene than in conventional (non-relativistic) 2D electron systems, as we will discuss in Sec. 2. This yields a "relativistic" quantum Hall effect with an unusual series for the Hall plateaus. Indeed rather than having plateaus with a quantised resistance according to  $R_H = h/e^2 n$ , with integer values of n, one finds plateaus with  $n = \pm 2(2n' + 1)$ , in terms of an integer n', i.e. with  $n = \pm 2, \pm 6, \pm 10, \ldots$  The different signs in the series  $(\pm)$  indicate that there are two different carriers,

<span id="page-14-1"></span> $^4$ The quantity n determines the filling of the LLs, usually described by the Greek letter  $\nu$ ,

of CFs rather than an IQHE of CFs.

as we will discuss in Sec. 2.

<span id="page-14-0"></span>1.1.6

<span id="page-15-0"></span>![](images/_page_15_Picture_0.jpeg)

<span id="page-15-1"></span>consequently gets filled with electrons [Fig. 1.4(c)]. One thus obtains a confinement potential of triangular shape for the electrons in the conduction band,

![](images/_page_16_Picture_0.jpeg)

metal

metal

 $\mathsf{E}_\mathsf{F}$ 

 $E_{F}$ 

oxide

insulator

oxide

insulator

represented in the inset II.

semiconductor

0000000000

semiconductor

••••••

conduction band acceptor

levels valence band

ź

conduction band

acceptor

levels

valence

ž

<span id="page-16-0"></span>Figure 1.4: MOSFET. The inset I shows a sketch of a MOSFET. (a) Level structure at  $V_G = 0$ . In the metallic part, the band is filled up to the Fermi energy  $E_F$  whereas the oxide is insulating. In the semiconductor, the Fermi energy lies in the band gap (energy gap between the valence and the conduction bands). Close to the valence band, albeit above  $E_F$ , are the acceptor levels. (b) The chemical potential in the metallic part may be controlled by the gate voltage  $V_G$  via the electric field effect. As a consequence of the introduction of holes the semiconductor bands are bent downwards, and above a threshold voltage (c), the conduction band is filled in the vicinity of the interface with the insulator. One thus obtains a 2D electron gas. Its confinement potential of which is of triangular shape, the levels (electronic subbands) of which are

band

metal

 $V_{G}$ 

 $\mathsf{E}_{\mathsf{F}}$ 

oxide (insulator)

II Е

Εı

2D electrons

.....

conduction band

levels

valence

ź

band

17

![](images/_page_17_Picture_0.jpeg)

<span id="page-17-1"></span>important in the study of the IQHE and FQHE, because the effects occur, as we will show below, when the 2D electronic density is on the order of the density of magnetic flux n<sup>B</sup> = B/(h/e) threading the system, in units of the flux quantum h/e. This needs to be compared to metals where the surface density is on the

the order of 1000 T) in order to probe the regime nel ∼ nB.

The mobility in MOSFETs, which is typically on the order of <sup>µ</sup> <sup>∼</sup> <sup>10</sup><sup>6</sup>

is limited by the quality of the oxide-semiconductor interface (surface roughness). This technical difficulty is circumvented in semiconductor heterostructures – most popular are GaAs/AlGaAs heterostructures – which are grown by molecular-beam epitaxy (MBE), where high-quality interfaces with almost atomic precision may be achieved, with mobilities on the order of <sup>µ</sup> <sup>∼</sup> <sup>10</sup><sup>7</sup> cm<sup>2</sup>/Vs. These mobilities were necessary to observe the FQHE, which was

<span id="page-17-0"></span>1.2.2 Semiconductor heterostructures

indeed first observed in a GaAs/AlGaAs sample [\[13\]](#page-114-12).

, which would require inaccessibly high magnetic fields (on

cm<sup>2</sup>/Vs,

order of 10<sup>14</sup> cm<sup>−</sup><sup>2</sup>

conduction band and where the density of states vanishes linearly.

viewed as a capacitor (Fig. 1.6) the capacitance of which is

In order to vary the Fermi energy in graphene, one usually places a graphene flake on a 300 nm thick insulating SiO<sub>2</sub> layer which is itself placed on top of a positively doped metallic silicon substrate (see Fig. 1.6). This sandwich structure, with the metallic silicon layer that serves as a backgate, may thus be

 $C = \frac{Q}{V_C} = \frac{\epsilon_0 \epsilon A}{d},$ 

where  $Q = en_{2D}A$  is the capacitor charge, in terms of the total surface A,  $V_G$  is the gate voltage, and d = 300 nm is the thickness of the SiO<sub>2</sub> layer with the

(1.14)

<span id="page-18-1"></span><span id="page-18-0"></span>1.2.3 Graphene

Graphene, a one-atom thick layer of graphite, presents a novel 2D electron system, which, from the electronic point of view, is either a zero-overlap semimetal or a zero-gap semiconductor, where the conduction and the valence bands are no longer separated by an energy gap. Indeed, in the absence of doping, the Fermi energy lies exactly at the points where the valence band touches the

![](images/_page_19_Picture_0.jpeg)

<span id="page-20-0"></span>![](images/_page_20_Picture_0.jpeg)

<span id="page-20-1"></span>In this section, we introduce the basic Hamiltonians which we treat in a quantummechanical manner in the following parts. Quite generally, we consider a Hamil-

p = (px, py) is a constant of motion, in the absence of a magnetic field. In quantum mechanics, this means that the momentum operator commutes with the Hamiltonian, [p, H] = 0, and that the eigenvalue of the momentum operator

In the case of a free particle, this is a very natural assumption, and one has for

<span id="page-20-3"></span><sup>1</sup>All vector quantities (also in the quantum-mechanical case of operators) v = (vx, vy) are

21

<span id="page-20-4"></span>H = p 2 2m

that is translation invariant, i.e. the momentum

, (2.1)

tonian for a 2D particle1

is a good quantum number.

the non-relativistic case,

hence 2D, unless stated explicitly.

<span id="page-20-2"></span>2.1.1 Hamiltonian of a free particle

<span id="page-21-3"></span>in terms of the particle mass m. 2 However, we are interested, here, in the motion of electrons in some material (in a metal or at the interface of to semiconductors). It seems, at first sight, to be a very crude assumption to describe the motion of an electron in a crystalline environment in the same manner as a particle in free space. Indeed, a particle in a lattice in not described by the Hamiltonian \(2.1\) but rather by the Hamiltonian

<span id="page-21-2"></span><span id="page-21-1"></span><span id="page-21-0"></span>H = p 2 2m + X N i V (r − ri), (2.2) where the last term represents the electrostatic potential caused by the ions situated at the lattice sites r<sup>i</sup> . Evidently, the Hamiltonian now depends on the position r of the particle with respect to that of the ions, and the momentum p is therefore no longer a constant of motion or a good quantum number. This problem is solved with the help of Bloch's theorem: although an arbitrary spatial translation is not an allowed symmetry operation as it is the case for a free particle \(2.1\), the system is invariant under a translation by an arbitrary lattice vector if the lattice is of infinite extension – an assumption we make here.3 In the same manner as for the free particle, where one defines the momentum as the generator of a spatial translation, one may then define a generator of a lattice translation. This generator is called the lattice momentum or also the quasi-momentum. As a consequence of the discreteness of the lattice translations, not all values of this lattice momentum are physical, but only those within the first Brillouin zone (BZ) – any vibrational mode, be it a lattice vibration or an electronic wave, with a wave vector outside the first BZ can be described by a mode with a wave vector within the first BZ. Since these lecture notes cannot include a full course on basic solid-state physics, we refer the reader to standard textbooks on solid-state physics \[25, [26\]](#page-115-12). The bottom line is that also in a (perfect) crystal, the electrons may be described in terms of a Hamiltonian H(px, py) if one keeps in mind that the momentum p in this expression is a lattice momentum restricted to the first BZ. Notice, however, that although the resulting Hamiltonian may often be written in the form \(2.1\), the mass is generally not the free electron mass but a band mass m<sup>b</sup> that takes into account the particular features of the energy bands4 – indeed, the mass may even depend on the direction of propagation, <sup>2</sup>The statement that p is a constant of motion remains valid also in the case of a relativistic particle. However, the Hamiltonian description depends on the frame of reference because the energy is not Lorentz-invariant, i.e. invariant under a transformation into another frame of reference that moves at constant velocity with respect to the first one. For this reason a Lagrangian rather than a Hamiltonian formalism is often prefered in relativistic quantum mechanics. <sup>3</sup>Although this may seem to be a typical "theoretician's assumption", it is a very good approximation when the lattice size is much larger than all other relevant length scales, such as the lattice spacing or the Fermi wave length. 4 In GaAs, e.g., the band mass is m<sup>b</sup> = 0.068m0, in terms of the free electron mass m0.

![](images/_page_22_Picture_0.jpeg)

<span id="page-22-1"></span>such that one should write the Hamiltonian more generally as

Dirac Hamiltonian in graphene

<span id="page-22-0"></span>2.1.2

 $H = \frac{p_x^2}{2m_x} + \frac{p_y^2}{2m_y} \ .$ 

The above considerations for electrons in a 2D lattice are only valid in the case of a Bravais lattice, i.e. a lattice in which all lattice sites are equivalent from a crystallographic point of view. However, some lattices, such as the honeycomb lattice that describes the arrangement of carbon atoms in graphene due to the  $\rm sp^2$  hybridisation of the valence electrons, are not Bravais lattices. In this case, one may describe the lattice as a Bravais lattice plus a particular pattern of  $N_s$  sites, called the basis. This is illustrated in Fig. 2.1(a) for the case of the honeycomb lattice. When one compares a site A (full circle) with a site B (empty circle), one notices that the environment of these two sites is different: whereas a site A has nearest neighbours in the directions north-east, north-west and south, a site B has nearest neighbours in the directions north, south-west and south-east. This precisely means that the two sites are not equivalent from a crystallographic point of view – although they may be equivalent from a chemical point of view, i.e. occupied by the same atom or ion type (carbon

![](images/_page_23_Picture_0.jpeg)

<span id="page-23-0"></span>tices, i.e. a basis with  $N_s$  sites, one needs to describe the general electronic wave function as a superposition of  $N_s$  different wave functions, which satisfy each Bloch's theorem for all sublattices [25, 26]. Formally, this may be described in terms of a  $N_s \times N_s$  matrix, the eigenvalues of which yield  $N_s$  different energy bands. In a lattice with  $N_s$  different sublattices, one therefore obtains one energy band per sublattice, and for graphene, one obtains two different bands for

<span id="page-23-1"></span> $H(\mathbf{k}) = t \begin{pmatrix} 0 & \gamma_{\mathbf{k}}^* \\ \gamma_{\mathbf{k}} & 0 \end{pmatrix},$ 

which is obtained within a tight-binding model, where one considers electronic hopping between nearest-neighbouring sites with a hopping amplitude t. Because the nearest neighbour of a site A is a site B and vice versa [see Fig. 2.1(a)], the Hamiltonian is off-diagonal, and the off-diagonal elements are related by complex conjugation due to time-reversal symmetry  $[H(-\mathbf{k})^* = H(\mathbf{k})]$ . As already mentioned above, the lattice momentum  $\mathbf{k}$  is restricted to the first BZ, which is of hexagonal shape and which we have depicted in Fig. 2.1(b) for

(2.3)

the conducting electrons, the valence band and the conduction band. The Hamiltonian for low-energy electrons in reciprocal space reads

![](images/_page_24_Picture_0.jpeg)

The analogy between electrons in graphene and massless relativistic particles is corroborated by a low-energy expansion of the Hamiltonian (2.3) around the contact points K and K', at the momenta  $\mathbf{K}$  and  $\mathbf{K}' = -\mathbf{K}$  [see Fig. 2.1(a)],  $\mathbf{k} = \pm \mathbf{K} + \mathbf{p}/\hbar$ , where  $|\mathbf{p}/\hbar| \ll |\mathbf{K}|$ . One may then expand the function  $\gamma_{\pm \mathbf{K} + \mathbf{p}/\hbar}$ 

 $H = t \begin{pmatrix} 0 & \nabla \gamma_{\mathbf{K}}^* \cdot \mathbf{p} \\ \nabla \gamma_{\mathbf{K}} \cdot \mathbf{p} & 0 \end{pmatrix} = v \begin{pmatrix} 0 & p_x - ip_y \\ p_x + ip_y & 0 \end{pmatrix} = v\mathbf{p} \cdot \boldsymbol{\sigma}$ 

 $\sigma^x = \left( \begin{array}{cc} 0 & 1 \\ 1 & 0 \end{array} \right), \qquad \sigma^y = \left( \begin{array}{cc} 0 & -i \\ i & 0 \end{array} \right) \qquad \text{and} \qquad \sigma^z = \left( \begin{array}{cc} 1 & 0 \\ 0 & -1 \end{array} \right)$ 

and where we have chosen to expand the Hamiltonian (2.3) around the K point.<sup>7</sup> Here, the Fermi velocity v plays the role of the velocity of light c, which is though roughly 300 times larger,  $c \simeq 300v$ . The details of the above derivation may be found in Appendix A. The above Hamiltonian is indeed formally that of massless 2D particles, and it is sometimes called Weyl or Dirac Hamiltonian.

 $^{5}$ Indeed, in graphene, the relevant low-energy scales are in the 10-100 meV regime, whereas non-linear corrections of the band dispersion become relevant in the eV regime.

<span id="page-24-2"></span><span id="page-24-1"></span><sup>7</sup>One obtains a similar result at the K' point, see Eq. (A.15) in Appendix A.

here.

to first order, and one obtains formally<sup>6</sup>

<span id="page-24-0"></span><sup>6</sup>Notice that  $\gamma_{\pm \mathbf{K}} = 0$  by symmetry.

where  $\boldsymbol{\sigma} = (\sigma^x, \sigma^y)$  in terms of the Pauli matrices

Landau Quantisation

<span id="page-25-0"></span>in order to account for a non-zero magnetic field.

momentum by its gauge-invariant form [27]

We will discuss, in the remainder of this chapter, how the two Hamiltonians

<span id="page-25-4"></span> $H_S = \frac{\mathbf{p}^2}{2m_L}$  and  $H_D = v\mathbf{p} \cdot \boldsymbol{\sigma}$ ,

for non-relativistic and relativistic particles, respectively, need to be modified

Hamiltonians for Non-Zero B Fields

Minimal coupling and Peierls substitution In order to describe free electrons in a magnetic field, one needs to replace the

<span id="page-25-2"></span> $\mathbf{p} \to \mathbf{\Pi} = \mathbf{p} + e\mathbf{A}(\mathbf{r}),$ 

26

where  $\mathbf{A}(\mathbf{r})$  is the vector potential that generates the magnetic field  $\mathbf{B} = \nabla \times$ 

<span id="page-25-1"></span>2.2

2.2.1

 $\mathbf{A}(\mathbf{r})$ . This gauge-invariant momentum is proportional the electron velocity v, which must naturally be gauge-invariant because it is a physical quantity.

Notice that because  $A(\mathbf{r})$  is not gauge invariant, neither is the momentum  $\mathbf{p}$ . Remember that adding the gradient of an arbitrary derivable function  $\lambda(\mathbf{r})$ ,  $\mathbf{A}(\mathbf{r}) \to \mathbf{A}(\mathbf{r}) + \nabla \lambda(\mathbf{r})$ , does not change the magnetic field because the rotational of a gradient is zero. Indeed, the momentum transforms as  $\mathbf{p} \to \mathbf{p} - e\nabla\lambda(\mathbf{r})$ under a gauge transformation in order to compensate the transformed vector potential, such that  $\Pi$  is gauge-invariant. The substitution (2.5) is also called

minimal substitution. In the case of electrons on a lattice, this substitution is more tricky because of the presence of several bands. Furthermore, the vector potential is unbound, even for a finite magnetic field; this becomes clear if one chooses a particular gauge, such as e.g. the Landau gauge  $\mathbf{A}_L(\mathbf{r}) = B(-y,0,0)$ , in which case the value of the vector potential may become as large as  $B \times L_y$ , where  $L_y$  is the macroscopic extension of the system in the y-direction. However, it may be

a is much smaller than the magnetic length

 $l_B = \sqrt{\frac{\hbar}{eB}}$ , which is the fundamental length scale in the presence of a magnetic field. Because a is typically an atomic scale ( $\sim 0.1$  to 10 nm) and  $l_B \simeq 26$  nm/ $\sqrt{B[T]}$ , this condition is fulfilled in all atomic lattices for the magnetic fields, which may be achieved in today's high-field laboratories ( $\sim 45$  T in the continuous regime and  $\sim 80$  T in the pulsed regime).

<span id="page-25-3"></span>the sample survives the experiment but not the coil that is used to produce the magnetic field.

shown that the substitution (2.5), which is called *Peierls substitution* in the context of electrons on a lattice, remains correct as long as the lattice spacing

(2.4)

(2.5)

(2.6)<sup>8</sup>Higher magnetic fields may be obtained only in semi-destructive experiments, in which

<span id="page-25-5"></span>

<span id="page-26-3"></span><span id="page-26-2"></span><span id="page-26-1"></span><span id="page-26-0"></span>

| На                                        | miltonians for Non-Zero B Fields                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | 27                                                                                                                      |
|-------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
|                                           | With the help of the (Peierls) substitution (2.5), one may thus it<br>ite down the Hamiltonian for charged particles in a magnetic<br>lows the Hamiltonian in the absence of a magnetic field,                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | · ·                                                                                                                     |
|                                           | $H(\mathbf{p}) \rightarrow H(\mathbf{\Pi}) = H(\mathbf{p} + e\mathbf{A}) = H^B(\mathbf{p}, \mathbf{r}).$                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |                                                                                                                         |
| ing<br>mo                                 | tice that because of the spatial dependence of the vector potential Hamiltonian is no longer translation invariant, and the (gauge mentum $\mathbf{p}$ is no longer a conserved quantity. We will limit the dependence B-field Hamiltonians corresponding to the Hamiltonians (2.4)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | -dependent)                                                                                                             |
|                                           | $H_S^B = \frac{[\mathbf{p} + e\mathbf{A}(\mathbf{r})]^2}{2m_b}$                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | (2.7)                                                                                                                   |
| for                                       | non-relativistic and                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |                                                                                                                         |
| c                                         | $H_D^B = v[\mathbf{p} + e\mathbf{A}(\mathbf{r})] \cdot \boldsymbol{\sigma}$                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | (2.8)                                                                                                                   |
| Ior                                       | relativistic 2D charged particles, respectively.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |                                                                                                                         |
| 2.5                                       | 2.2 Quantum mechanical treatment                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |                                                                                                                         |
| me $tio$ sta with $[\mathcal{O}]$ sai qua | order to analyse the one-particle Hamiltonians (2.7) and (2.8) in schanical treatment, we use the standard method, the canonic in [28], where one interprets the physical quantities as operators to vectors in a Hilbert space. These operators do in general near describe the physical system. Formally one introduces the eat describe the physical system. Formally one introduces the describe the physical system. Formally one introduces the describe the physical system the two operators $\mathcal{O}_1$ and $\mathcal{O}_2$ depends to commute when $[\mathcal{O}_1, \mathcal{O}_2] = 0$ or else not to commute. The balantities in the argument of the Hamiltonian are the 2D position $\mathbf{r}$ canonical momenta $\mathbf{p} = (p_x, p_y)$ , which satisfy the commutation | al quantisa-<br>that act on<br>ot commute<br>state vector<br>commutator<br>x, which are<br>asic physical<br>x = $x$ and |
| i.e. me pos acc me $\Delta y$             | each component of the position operator does not commute we entum in the corresponding direction. This non-commutativity sition and its associated momentum is the origin of the Heisenber cording to which one cannot know precisely both the position of chanical particle and, at the same moment, its momentum, $\Delta x \Delta t \Delta t \Delta t \Delta t \Delta t \Delta t \Delta t \Delta t \Delta t $                                                                                                                                                                                                                                                                                                                                                                              | (2.9) with the mobetween the reg inequality a quantum- $\Delta p_x \gtrsim h$ and                                       |
|                                           | $[\Pi_x, \Pi_y] = [p_x + eA_x(\mathbf{r}), p_y + eA_y(\mathbf{r})] = e([p_x, A_y] - [p_y, A_x])$ $= e\left(\frac{\partial A_y}{\partial x}[p_x, x] + \frac{\partial A_y}{\partial y}[p_x, y] - \frac{\partial A_x}{\partial x}[p_y, x] - \frac{\partial A_x}{\partial y}[p_y, x]\right)$                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | = -                                                                                                                     |
|                                           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |                                                                                                                         |
|                                           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |                                                                                                                         |
|                                           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |                                                                                                                         |

where we have used the relation9

<span id="page-27-2"></span>
$$[\mathcal{O}_1, f(\mathcal{O}_2)] = \frac{df}{d\mathcal{O}_2}[\mathcal{O}_1, \mathcal{O}_2]$$
 (2.10)

between two arbitrary operators, the commutator of which is a c-number or an operator that commutes itself with both O<sup>1</sup> and O<sup>2</sup> [\[28\]](#page-115-14). With the help of the commutation relations \(2.9\), one finds that

$$[\Pi_x, \Pi_y] = -ie\hbar \left( \frac{\partial A_y}{\partial x} - \frac{\partial A_x}{\partial y} \right) = -ie\hbar \left( \nabla \times \mathbf{A} \right)_z = -ie\hbar B,$$

and, in terms of the magnetic length \(2.6\),

<span id="page-27-1"></span>
$$[\Pi_x, \Pi_y] = -i\frac{\hbar^2}{l_B^2} \ .$$
 (2.11)

This equation is the basic result of this section and merits some further discussion.

- As one would have expected for gauge-invariant quantities (the two components of Π), their commutator is itself gauge-invariant. Indeed, it only depends on universal constants and the (gauge-invariant) magnetic field B, and not on the vector potential A.
- The components of the gauge-invariant momentum Π are mutually conjugate in the same manner as x and p<sup>x</sup> or y and py. Remember that p<sup>x</sup> generates the translations in the x-direction (and p<sup>y</sup> those in the y-direction). This is similar here: Π<sup>x</sup> generates a "boost" of the gauge-invariant momentum in the y-direction, and similarly Π<sup>y</sup> one in the x-direction.
- As a consequence, one may not diagonalise at the same time Π<sup>x</sup> and Πy, in contrast to the zero-field case, where the arguments of the Hamiltonian, p<sup>x</sup> and py, commute.

For solving the Hamiltonians \(2.7\) and \(2.8\), it is convenient to use the pair of conjugate operators Π<sup>x</sup> and Π<sup>y</sup> to introduce ladder operators in the same manner as in the quantum-mechanical treatment of the one-dimensional harmonic oscillator. Remember from your basic quantum-mechanics class that the ladder operators may be viewed as the complex position of the one-dimensional oscillator in the phase space, which is spanned by the position (x-axis) and the momentum (y-axis),

$$\tilde{a} = \frac{1}{\sqrt{2}} \left( \frac{x}{x_0} - i \frac{p}{p_0} \right)$$
 and  $\tilde{a}^{\dagger} = \frac{1}{\sqrt{2}} \left( \frac{x}{x_0} + i \frac{p}{p_0} \right)$ ,

$$[\mathcal{O}_0, f(\mathcal{O}_1, ..., \mathcal{O}_J)] = \sum_{j=1}^J \frac{\partial f}{\partial \mathcal{O}_j} [\mathcal{O}_0, \mathcal{O}_j]$$

which is valid if [[O0, Oj ], O0] = [[O0, Oj ], Oj ] = 0 for all j = 1, ...,N.

<span id="page-27-0"></span><sup>9</sup>More precisely we have used a gradient generalisation of this relation to operator functions that depend on several different operators,

Landau Levels 29

where  $x_0 = \sqrt{\hbar/m_b\omega}$  and  $p_0 = \sqrt{\hbar m_b\omega}$  are normalisation constants in terms of the oscillator frequency  $\omega$  [28]. The fact that the position x and the momentum p are conjugate variables and the particular choice of the normalisation constants yields the commutation relation  $[\tilde{a}, \tilde{a}^{\dagger}] = 1$  for the ladder operators.

In the case of the 2D electron in a magnetic field, the ladder operators play the role of a *complex* gauge-invariant momentum (or velocity), and they read

<span id="page-28-2"></span>
$$a = \frac{l_B}{\sqrt{2}\hbar} (\Pi_x - i\Pi_y)$$
 and  $a^{\dagger} = \frac{l_B}{\sqrt{2}\hbar} (\Pi_x + i\Pi_y)$ , (2.12)

where we have chosen the appropriate normalisation such as to obtain the usual commutation relation

<span id="page-28-4"></span>
$$[a, a^{\dagger}] = 1. \tag{2.13}$$

It turns out to be helpful for future calculations to invert the expression for the ladder operators (2.12),

<span id="page-28-3"></span>
$$\Pi_x = \frac{\hbar}{\sqrt{2}l_B} \left( a^{\dagger} + a \right) \quad \text{and} \quad \Pi_y = \frac{\hbar}{i\sqrt{2}l_B} \left( a^{\dagger} - a \right).$$
(2.14)

#### <span id="page-28-0"></span>2.3 Landau Levels

The considerations of the preceding section are extremely useful in the calculation of the level spectrum associated with the Hamiltonians (2.7) and (2.8) of both the non-relativistic and the relativistic particles, respectively. The understanding of this level spectrum is the issue of the present section. Because electrons do not only possess a charge but also a spin, each level is split into two spin branches separated by the energy difference  $\Delta_Z \epsilon = g\mu_B B$ , where g is the g-factor of the host material and  $\mu_B = e\hbar/2m_0$  the Bohr magneton. In order to simplify the following presentation of the quantum-mechanical treatment and the level structure, we neglect this effect associated with the spin degree of freedom. Formally, this amounts to considering spinless fermions. Notice, however, that there exist interesting physical properties related to the spin degree of freedom, which will be treated separately in Chap. 5.

#### <span id="page-28-1"></span>2.3.1 Non-relativistic Landau levels

In terms of the gauge-invariant momentum, the Hamiltonian (2.7) for non-relativistic electrons reads

$$H_S^B = \frac{1}{2m_b} \left( \Pi_x^2 + \Pi_y^2 \right).$$

The analogy with the one-dimensional harmonic oscillator is apparent if one notices that both conjugate operators  $\Pi_x$  and  $\Pi_y$  occur in this expression in a quadratic form. If one replaces these operators with the ladder operators (2.14),

one obtains, with the help of the commutation relation (2.13),

<span id="page-29-1"></span>
$$H_S^B = \frac{\hbar^2}{4ml_B^2} \left[ a^{\dagger 2} + a^{\dagger} a + a a^{\dagger} + a^2 - \left( a^{\dagger 2} - a^{\dagger} a - a a^{\dagger} + a^2 \right) \right]$$

$$= \frac{\hbar^2}{2ml_B^2} \left( a^{\dagger} a + a a^{\dagger} \right) = \frac{\hbar^2}{ml_B^2} \left( a^{\dagger} a + \frac{1}{2} \right)$$

$$= \hbar \omega_C \left( a^{\dagger} a + \frac{1}{2} \right), \qquad (2.15)$$

where we have used the relation  $\omega_c = \hbar/m_b l_B^2$  between the cyclotron frequency (1.2) and the magnetic length (2.6) in the last step.

As in the case of the one-dimensional harmonic oscillator, the eigenvalues and eigenstates of the Hamiltonian (2.15) are therefore those of the number operator  $a^{\dagger}a$ , with  $a^{\dagger}a|n\rangle = n|n\rangle$ . The ladder operators act on these states in the usual manner [28]

<span id="page-29-5"></span>
$$a^{\dagger}|n\rangle = \sqrt{n+1}|n+1\rangle$$
 and  $a|n\rangle = \sqrt{n}|n-1\rangle$ , (2.16)

where the last equation is valid only for n > 0 – the action of a on the ground state  $|0\rangle$  gives zero,

<span id="page-29-3"></span>
$$a|0\rangle = 0. (2.17)$$

This last equation turns out to be helpful in the calculation of the eigenstates associated with the level of lowest energy, as well as the construction of states in higher levels n (see Sec. 2.4.1)

<span id="page-29-4"></span>
$$|n\rangle = \frac{\left(a^{\dagger}\right)^n}{\sqrt{n!}}|0\rangle. \tag{2.18}$$

The energy levels of the 2D charged non-relativistic particle are therefore discrete and labelled by the integer n,

$$\epsilon_n = \hbar\omega_C \left( n + \frac{1}{2} \right). \tag{2.19}$$

These levels, which are also called *Landau levels* (LL), are depicted in Fig. 2.3(a) as a function of the magnetic field. Because of the linear field-dependence of the cyclotron frequency, the LLs disperse linearly themselves with the magnetic field.

#### <span id="page-29-0"></span>2.3.2 Relativistic Landau levels

The relativistic case (2.8) for electrons in graphene may be treated exactly in the same manner as the non-relativistic one. In terms of the ladder operators (2.12), the Hamiltonian reads

<span id="page-29-2"></span>
$$H_D^B = v \begin{pmatrix} 0 & \Pi_x - i\Pi_y \\ \Pi_x + i\Pi_y & 0 \end{pmatrix} = \sqrt{2} \frac{\hbar v}{l_B} \begin{pmatrix} 0 & a \\ a^{\dagger} & 0 \end{pmatrix}. \tag{2.20}$$

Landau Levels 31

![](images/_page_30_Figure_1.jpeg)

<span id="page-30-0"></span>Figure 2.3: Landau levels as a function of the magnetic field. (a) Non-relativistic case with  $\epsilon_n = \hbar \omega_C (n+1/2) \propto B(n+1/2)$ . (b) Relativistic case with  $\epsilon_{\lambda,n} = \lambda (\hbar v/l_B) \sqrt{2n} \propto \lambda \sqrt{Bn}$ .

One notices the occurrence of a characteristic frequency  $\omega' = \sqrt{2}v/l_B$ , which plays the role of the cyclotron frequency in the relativistic case. Notice, however, that this frequency may not be written in the form  $eB/m_b$  because the band mass is strictly zero in graphene, such that the frequency would diverge.<sup>10</sup>

In order to obtain the eigenvalues and the eigenstates of the Hamiltonian (2.20), one needs to solve the eigenvalue equation  $H_D^B \psi_n = \epsilon_n \psi_n$ . Because the Hamiltonian is a  $2 \times 2$  matrix, the eigenstates are 2-spinors,

$$\psi_n = \left(\begin{array}{c} u_n \\ v_n \end{array}\right),$$

and we thus need to solve the system of equations

<span id="page-30-2"></span>
$$\hbar\omega' a v_n = \epsilon_n u_n \quad \text{and} \quad \hbar\omega' a^{\dagger} u_n = \epsilon_n v_n , \qquad (2.21)$$

which yields the equation

$$a^{\dagger}a \, v_n = \left(\frac{\epsilon_n}{\hbar \omega'}\right)^2 v_n \tag{2.22}$$

for the second spinor component. One notices that this component is an eigenstate of the number operator  $n=a^{\dagger}a$ , which we have already encountered in the preceding subsection. We may therefore identify, up to a numerical factor, the second spinor component  $v_n$  with the eigenstate  $|n\rangle$  of the non-relativistic Hamiltonian (2.15),  $v_n \sim |n\rangle$ . Furthermore, one observes that the square of the

<span id="page-30-1"></span> $<sup>^{10}</sup>$  Sometimes, a cyclotron mass  $m_C$  is formally introduced via the equality  $\omega' \equiv eB/m_C$ . However, this mass is a somewhat artificial quantity, which turns out to depend on the carrier density. We will therefore not use this quantity in the present lecture notes.

energy is proportional to this quantum number,  $\epsilon_n^2 = (\hbar \omega')^2 n$ . This equation has two solutions, a positive and a negative one, and one needs to introduce another quantum number  $\lambda = \pm$ , which labels the states of positive and negative energy, respectively. This quantum number plays the same role as the band index ( $\lambda = +$  for the conduction and  $\lambda = -$  for the valence band) in the zero-B-field case discussed in Sec. 2.1. One thus obtains the level spectrum [29]

$$\epsilon_{\lambda,n} = \lambda \frac{\hbar v}{l_B} \sqrt{2n} \tag{2.23}$$

the energy levels of which are depicted in Fig. 2.3(b). These relativistic Landau levels disperse as  $\lambda \sqrt{Bn}$  as a function of the magnetic field.

Once we know the second spinor component, the first spinor component is obtained from Eq. (2.21), which reads  $u_n \propto a \, v_n \sim a |n\rangle \sim |n-1\rangle$ . One then needs to distinguish the zero-energy LL (n=0) from all other levels. Indeed, for n=0, the first component is zero as one may see from Eq. (2.17). In this case one obtains the spinor

<span id="page-31-1"></span>
$$\psi_{n=0} = \begin{pmatrix} 0 \\ |n=0\rangle \end{pmatrix}. \tag{2.24}$$

In all other cases  $(n \neq 0)$ , one has positive and negative energy solutions, which differ among each other by a relative sign in one of the components. A convenient representation of the associated spinors is given by

$$\psi_{\lambda,n\neq 0} = \frac{1}{\sqrt{2}} \begin{pmatrix} |n-1\rangle \\ \lambda|n\rangle \end{pmatrix}. \tag{2.25}$$

#### Experimental observation of relativistic Landau levels

Relativistic LLs have been observed experimentally in transmission spectroscopy, where one shines light on the sample and measures the intensity of the transmitted light. Such experiments have been performed on so-called epitaxial graphene<sup>11</sup> [31] and later on exfoliated graphene [32]. When the monochromatic light is in resonance with a dipole-allowed transition from the (partially) filled LL  $(\lambda, n)$  to the (partially) unoccupied LL  $(\lambda', n \pm 1)$ , the light is absorbed due to an electronic excitation between the two levels [see Fig. 2.4(a)]. Notice that, in a non-relativistic 2D electron gas, the only allowed dipolar transition is that from the last occupied LL n to the first unoccupied one n + 1. The transition energy is  $\hbar\omega_C$ , independently of n, and one therefore observes a single absorbtion line (cyclotron resonance). In graphene, however, there are many more allowed transitions due to the presence of two electronic bands, the conduction and the valence band, and the transitions have the energies

$$\Delta_{n,\xi} = \frac{\hbar v}{l_B} \left[ \sqrt{2(n+1)} - \xi \sqrt{2n} \right],$$

<span id="page-31-0"></span><sup>&</sup>lt;sup>11</sup>Epitaxial graphene is obtained from a thermal graphitisation process of an epitaxially grown SiC crystal [30]

![](images/_page_32_Picture_0.jpeg)

 $\begin{array}{c|ccccccccccccccccccccccccccccccccccc$ 

Figure 2.4: LL spectroscopy in graphene (from (Sadowski et al., 2006). (a)
For a fixed magnetic field (0.4 T), one observes resonances in the transmission spectrum as a function of the irradiation energy. The resonances are associated with allowed dipolar transitions between relativistic LLs. (b) These resonances

<span id="page-32-0"></span>are shifted as a function of the magnetic field. (c) If one plots the resonance

energies as a function of the square root of the magnetic field,  $\sqrt{B}$ , a linear dependence is observed as one would expect for relativistic LLs.

![](images/_page_33_Picture_0.jpeg)

<span id="page-33-0"></span>Hamiltonian and which therefore gives rise to the *level degeneracy* of the LLs – in addition to the degeneracy due to internal degrees of freedom such as the

 $\tilde{\mathbf{\Pi}} = \mathbf{p} - e\mathbf{A}(\mathbf{r}),$ 

which we call *pseudo-momentum* to give a name to this operator. One may then express the momentum operator  $\mathbf{p}$  and the vector potential  $\mathbf{A}(\mathbf{r})$  in terms

<span id="page-33-3"></span> $\mathbf{p} = \frac{1}{2}(\mathbf{\Pi} + \tilde{\mathbf{\Pi}})$  and  $\mathbf{A}(\mathbf{r}) = \frac{1}{2c}(\mathbf{\Pi} - \tilde{\mathbf{\Pi}}).$ 

Notice that, in contrast to the gauge-invariant momentum, the pseudo-momentum depends on the gauge and, therefore, does not represent a physical quantity.<sup>13</sup> However, the commutator between the two components of the pseudo-momentum

<span id="page-33-4"></span> $\left[\tilde{\Pi}_x, \tilde{\Pi}_y\right] = i \frac{\hbar^2}{l_P^2} \ .$ 

<span id="page-33-1"></span> $^{12}$ The quantum states are naturally only degenerate if one neglects the Zeeman effect.  $^{13}$ We will nevertheless try to give a physical interpretation to this operator below, within a

In analogy with the gauge-invariant momentum,  $\Pi = \mathbf{p} + e\mathbf{A}(\mathbf{r})$ , we consider

(2.26)

(2.27)

(2.28)

spin<sup>12</sup> or, in the case of graphene, the two-fold valley degeneracy.

the same combination with the opposite relative sign,

of  $\Pi$  and  $\Pi$ ,

<span id="page-33-2"></span>semi-classical picture.

turn out to be gauge-invariant,

<span id="page-34-0"></span>![](images/_page_34_Picture_0.jpeg)

<span id="page-34-2"></span>for which the last of the mixed commutators (2.29) would not vanish. This gauge choice may even occur simpler: because the vector potential only depends on the y-component of the position, the system remains then translation invariant in the x-direction. Therefore, the associated momentum  $p_x$  is a good quantum number, which may be used to label the quantum states in addition to the LL quantum number n. For the Landau gauge, which is useful in the description of geometries with translation invariance in the y-direction, the wave functions are calculated in Sec. (2.4.2). However, the symmetric gauge, the wave functions of which are presented in Sec. (2.4.1), plays an important role in two different aspects; first, it allows for a semi-classical interpretation more easily than the Landau gauge, and second, the wave functions obtained from the symmetric gauge happen to be the basic ingredient in the construction of trial wave functions à la Laughlin for the description of the FQHE, as we will

The pseudo-momentum, with its mutually conjugate components  $\Pi_x$  and  $\Pi_y$ , allows us to introduce, in the same manner as for the gauge-invariant momentum

(2.32)

<span id="page-34-1"></span> $b = \frac{l_B}{\sqrt{2}\hbar} \left( \tilde{\Pi}_x + i\tilde{\Pi} \right)$  and  $b^{\dagger} = \frac{l_B}{\sqrt{2}\hbar} \left( \tilde{\Pi}_x - i\tilde{\Pi} \right)$ ,

see in Chap. 4.

 $\Pi$ , ladder operators,

36 Landau Quantisation

η B r R Figure 2.5: Cyclotron motion of an electron in a magnetic field around the guiding centre R. The grey region indicates the quantum-mechanical uncertainty of the guiding-centre position due to the non-commutativity \(2.39\) of its

<span id="page-35-1"></span>components. which again satisfy the usual commutation relations [b, b† ] = 1 and which, in the symmetric gauge, commute with the ladder operators a and a † , [b, a(†) ] = 0, and thus with the Hamiltonian, [b (†) , HB] = 0. One may then introduce a number † b associated with these ladder operators, the eigenstates of which

operator b satisfy the eigenvalue equation b † b|mi = m|mi. One thus obtains a second quantum number, an integer m ≥ 0, which is necessary to describe, as expected from the above dimensional argument, the full

quantum states in addition to the LL quantum number n. The quantum states therefore become tensor products of the two Hilbert vectors |n, mi = |ni ⊗ |mi (2.33) for non-relativistic particles. In the relativistic case, one has

ψλn,m = ψλn,m ⊗ |mi = 1 √ 2 |n − 1, mi λ|n, mi (2.34) for n 6= 0 and 0 

<span id="page-35-3"></span><span id="page-35-2"></span><span id="page-35-0"></span>ψn=0,m = ψn=0 ⊗ |mi =

|n = 0, mi

(2.35)

for the zero-energy LL. 2.3.4 Semi-classical interpretation of the level degeneracy How can we illustrate this somewhat mysterious pseudo-momentum introduced formally above? Remember that, because the pseudo-momentum is a gaugedependent quantity, any physical interpretation needs to be handled with care.

![](images/_page_36_Picture_0.jpeg)

<span id="page-36-1"></span><span id="page-36-0"></span>of its centre R, which we call guiding centre from now on, as one would expect

The postions x and y may then be expressed in terms of the momenta Π and

Π˜ y eB + Π<sup>y</sup> eB .

This means that, in the symmetric gauge, the components of the pseudomomentum are nothing other, apart from a factor to translate a momentum

and Y =

Π˜ x eB − Π<sup>x</sup> eB

In order to relate the guiding centre R to the pseudo-momentum Π˜ , we use

(<sup>Π</sup> <sup>−</sup> Π˜ ).

Π˜ x eB

. (2.38)

from the translational invariance of the equations of motion \(2.36\).

2 −y x = 1 2

y =

Π˜ y eB

x = −

A comparison of these expresssions with Eq. \(2.37\) allows us to identify

Eq. \(2.27\) for the vector potential in the symmetric gauge,

<sup>e</sup>A(r) = eB

<span id="page-36-2"></span>X = −

Π˜ ,

![](images/_page_37_Picture_0.jpeg)

<span id="page-37-3"></span><span id="page-37-2"></span><span id="page-37-0"></span>scopically degenerate. We will show in a more quantitative manner than in the above argument based on the Heisenberg inequality that the number of states per LL is indeed given by  $N_B$  when discussing, in the next section, the electronic

Similarly to the guiding-centre operator, we may introduce the *cyclotron* variable  $\eta = (\eta_x, \eta_y)$ , which determines the cyclotron motion and which fully describes the dynamic properties. The cyclotron variable is perpendicular to the electron's velocity and may be expressed in terms of the gauge-invariant

 $\eta_x = \frac{\Pi_y}{eB} \quad \text{and} \quad \eta_y = -\frac{\Pi_x}{eB} ,$ 

as one sees from Eq. (2.37). The position of the electron is thus decomposed into its guiding centre and its cyclotron variable,  $\mathbf{r} = \mathbf{R} + \boldsymbol{\eta}$ . Also the components of the cyclotron variable do not commute, and one finds with the help of Eq.

 $[\eta_x, \eta_y] = \frac{[\Pi_x, \Pi_y]}{(eB)^2} = -il_B^2 = -[X, Y].$ 

<span id="page-37-1"></span> $^{14}$ Mathematicians speak of a non-commutative geometry in this context, and the charged

(2.42)

(2.43)

wave functions in the symmetric and the Landau gauges.

2D particle may be viewed as a pardigm of this concept.

momentum  $\Pi$ ,

(2.11)

<span id="page-38-5"></span>Eigenstates 39 Until now, we have only discussed a single particle and its possible quantum states. Consider now N independent quantum-mechanical electrons at zerotemperature. In the absence of a magnetic field, electrons in a metal, due to their fermionic nature and the Pauli principle which prohibits double occupancy of a single quantum state, fill all quantum states up to the Fermi energy, which depends thus on the number of electrons itself. The situation is similar in the presence of a magnetic field: the electrons preferentially occupy the lowest LLs, i.e. those of lowest energy. But once a LL is filled, the remaining electrons are forced to populate higher LLs. In order to describe the LL filling it is therefore useful to introduce the dimensionless ratio between the number of electrons  $N_{el} = n_{el} \times \mathcal{A}$  and that of the flux quanta,  $\nu = \frac{N_{el}}{N_B} = \frac{n_{el}}{n_B} = \frac{hn_{el}}{eB},$ (2.44)which is called filling factor. Indeed the integer part,  $[\nu]$ , of the filling factor counts the number of completely filled LLs. Notice that one may vary the filling factor either by changing the particle number or by changing the magnetic field. At fixed particle number, lowering the magnetic field corresponds to an increase of the filling factor. 2.4 Eigenstates 2.4.1Wave functions in the symmetric gauge The algebraic tools established above may be used calculate the electronic wave functions, which are the space representations of the quantum states  $|n,m\rangle$ ,  $\phi_{n,m}(x,y) = \langle x,y|n,m\rangle$ . Notice first that one may obtain all quantum state  $|n,m\rangle$  from a single state  $|n=0,m=0\rangle$ , with the help of  $|n,m\rangle = \frac{\left(a^{\dagger}\right)^n}{\sqrt{n!}} \frac{\left(b^{\dagger}\right)^m}{\sqrt{m!}} |n=0,m=0\rangle,$ (2.45)which is a generalisation of Eq. (2.18). Naturally, this equation translates into a differential equation for the wave functions  $\phi_{n,m}(x,y)$ . A state in the lowest LL (n = 0) is characterised by the condition (2.17)

<span id="page-38-4"></span><span id="page-38-3"></span> $a|n=0,m\rangle=0,$ 

<span id="page-38-1"></span><span id="page-38-0"></span>which needs to be translated into a differential equation. Remember from Eq. (2.12) that  $a = (l_B/\sqrt{2}\hbar)(\Pi_x - i\Pi_y)$  and, by definition,  $\mathbf{\Pi} = -i\hbar\nabla + e\mathbf{A}(\mathbf{r})$  where we have already represented the momentum as a differential operator in

 $a = -i\sqrt{2} \left[ \frac{l_B}{2} \left( \partial_x - i\partial_y \right) + \frac{x - iy}{4l_B} \right],$ 

<span id="page-38-2"></span> $^{15}$  We limit the discussion to the non-relativistic case. The spinor wave functions for rela-

tivistic electrons are then easily obtained with the help of Eqs. (2.34) and (2.35).

position representation,  $\mathbf{p} = -i\hbar\nabla$ . One then finds

(2.46)

![](images/_page_39_Picture_0.jpeg)

<span id="page-39-0"></span> $(z^* + 4l_B^2 \partial) \phi'_{m-0}(z, z^*) = 0$ 

 $\phi'_{m=0}(z,z^*)=g(z^*)e^{-|z|^2/4l_B^2},$  in terms of an anti-analytic function  $g(z^*)$  with  $\partial g(z^*)=0$ . The wave function  $\phi_{n=0,m=0}(z,z^*)$  must therefore be the Gaussian with a prefactor that is both analytic and anti-analytic, i.e. a constant that is fixed by the normalisation.

 $\phi_{n=0,m=0}(z,z^*) = \langle z,z^*|n=0,m=0\rangle = \frac{1}{\sqrt{2\pi l_B^2}}e^{-|z|^2/4l_B^2},$ 

and a lowest-LL state with arbitrary m may then be obtained with the help of

 $\phi_{n=0,m}(z,z^*) = \frac{i^m \sqrt{2^m}}{\sqrt{2\pi l_B^2 m!}} \left(\frac{z}{4l_B} - l_B \bar{\partial}\right)^m e^{-|z|^2/4l_B^2}$ 

 $= \frac{i^m}{\sqrt{2\pi l_P^2 m!}} \left(\frac{z}{\sqrt{2}l_P}\right)^m e^{-|z|^2/4l_B^2}.$ 

(2.50)

(2.51)

with the solution

One finds

Eq. (2.45),

![](images/_page_40_Picture_0.jpeg)

of a disc. Consider the disc to have a radius  $R_{max}$  (and a surface  $\mathcal{A} = \pi R_{max}^2$ ). How many quantum states may be accommodated within the circle? The quantum state with maximal m quantum number, which we call M, has a radius  $l_B\sqrt{2M+1}$ , which must naturally coincide with the radius  $R_{max}$  of the disc. One therefore obtains  $\mathcal{A} = \pi l_B^2(2M+1)$ , and the number of states within the

<span id="page-40-1"></span> $M = \frac{\mathcal{A}}{2\pi l_B^2} = n_B \times \mathcal{A} = N_B,$ 

in agreement with the result (2.41) obtained from the argument based on the

If the sample geometry is rectangular, the Landau gauge (2.31),  $\mathbf{A}_L(\mathbf{r}) = B(-y,0,0)$ , is more appropriate than the symmetric gauge to describe the physical system. As already mentioned above, the momentum  $p_x = \hbar k$  is a good

Wave functions in the Landau gauge

(2.54)

disc is then, in the thermodynamic limit  $M \gg 1$ ,

<span id="page-40-0"></span>Heisenberg uncertainty relation.

<span id="page-41-1"></span><span id="page-41-0"></span> $y_0 = kl_B^2$ .

(2.56)

quantum number due to translational invariance in the x-direction. One may therefore use a plane-wave ansatz  $\psi_{n,k}(x,y)=\frac{e^{ikx}}{\sqrt{L}}\chi_{n,k}(y),$  for the wave functions. In this case, the Hamiltonian (2.7) becomes

for the wave functions. In this case, the Hamiltonian (2.7) becomes  $H_S^B = \frac{(p_x - eBy)^2}{2m} + \frac{p_y^2}{2m} = \frac{p_y^2}{2m} + \frac{1}{2}m\omega_C(y - y_0)^2, \qquad (2.55)$ where we have defined

The Hamiltonian (2.55) is nothing other than the Hamiltonian of a one-dimensional oscillator centred around the position  $y_0$ , and the eigenstates are  $\chi_{n,k}(y) = H_n\left(\frac{y-y_0}{l_B}\right)e^{-(y-y_0)^2/4l_B^2},$  in terms of Hermite polynomials  $H_n(x)$  [28]. The coordinate  $y_0$  plays the role of the guiding centre component Y, the component X being smeared over the whole sample length L, as it is dictated by the Heisenberg uncertainty relation

whole sample length L, as it is dictated by the Heisenberg uncertainty relation resulting from the commutation relation (2.39)  $[X,Y]=il_B^2$ .

Using periodic boundary conditions  $k=m\times 2\pi/L$  for the wave vector in the x-direction, one may count the number of states in a rectangular surface of length L and width W (in the y-direction), similarly to the above arguments in the symmetric gauge. Consider the sample to range from  $y_{min}=0$  to  $y_{max}=W$ , the first corresponding via the above-mentioned condition (2.56) to the wave vector k=0 and the latter to a wave vector  $k_{max}=M\times 2\pi/L$ . Two neighbouring quantum states are separated by the distance  $\Delta y=\Delta k l_B^2=\Delta m(2\pi/L)l_B^2=2\pi l_B^2/L$ , and each state therefore occupies a surface  $\sigma=\Delta y\times L=2\pi l_B^2$ , which agrees with the result (2.40) obtained above with the help of the

 $\Delta m(2\pi/L)l_B^2 = 2\pi l_B^2/L$ , and each state therefore occupies a surface  $\sigma = \Delta y \times L = 2\pi l_B^2$ , which agrees with the result (2.40) obtained above with the help of the consideration based on the Heisenberg uncertainty relation. The total number of states is, as in the symmetric gauge and the general argument leading to Eq. (2.41),  $M = N_B = n_B \times LW = n_B \times \mathcal{A},$ i.e. the number of flux quanta threading the (rectangular) surface  $\mathcal{A} = LW$ .

<span id="page-42-0"></span>![](images/_page_42_Picture_0.jpeg)

In the present chapter, we discuss the transport properties of electrons in the IQHE, namely the somewhat mysterious role that disorder plays in this type of transport. Remember from the introduction that the Hall resistance is quan-

standard of resistance see Eq. [\(1.13\)]. The resistance quantisation in the IQHE therefore does reflect neither a particular disorder distribution nor a particular sample geometry. Nevertheless, disorder turns out to play an essential role in

We will first consider, in Sec. 3.1, the motion of a 2D electron in a perpendicular magnetic field when also an external electrostatic potential is present, such as the one generated by disorder or the confinement potential that defines the sample boundaries. In Sec. 3.2, we then calculate the conductance of a single LL within a mesoscopic picture and discuss the difference between a twoterminal and a six-terminal transport measurement in Sec. 3.3. Furthermore, we discuss, in Sec. 3.4, the IQHE within a percolation picture and present some scaling properties that characterise the plateau transitions. We terminate this chapter with a short discussion of the pecularities of the relativistic quantum Hall effect in graphene the understanding of which requires essentially the same

), such that it is now used as the

tised with an astonishingly high precision (10<sup>−</sup><sup>9</sup>

the occurence of the IQHE, as we will see in this chapter.

ingredients as the IQHE in non-relativistic quantum Hall systems.

43

![](images/_page_43_Picture_0.jpeg)

<span id="page-43-0"></span>is the typical length scale for the variation of the electrostatic potential. The sample is confined in the y-direction between  $y_{max}$  and  $y_{min}$ . The thin lines indicate the equipotential lines. When approaching one of the sample edges, they become parallel to the edge. The grey lines indicate the electronic motion with the guiding centre moving along the equipotential lines. The electron turns clockwise around a summit of the potential landscape, which is caused e.g. by a negatively charged impurity (-), and counter-clockwise around a valley (+). At the sample edges, the equipotential lines due to the confinement potential

connect the two contacts on the left and on the right hand side.

<span id="page-44-0"></span>![](images/_page_44_Picture_0.jpeg)

<span id="page-44-3"></span><span id="page-44-1"></span>In a first step, we consider a potential  $V(\mathbf{r})$  that varies smoothly on the scale set by the magnetic length, i.e.  $\xi \gg l_B$ , where  $\xi$  describes the characteristic length scale for the variation of  $V(\mathbf{r})$ . Notice first that the external electrostatic potential lifts the LL degeneracy because the Hamiltonian  $H = H_B + V(\mathbf{r} = \mathbf{R} + \boldsymbol{\eta})$  no longer commutes with the guiding-centre operator  $\mathbf{R}$ , in contrast to the "free" Hamiltonian  $H_B$ ,  $[H, \mathbf{R}] = [V, \mathbf{R}] \neq 0$ . Physically, this is not unexpected: the guiding centre is a constant of motion due to translation invariance, i.e. it does not matter whether the electron performs its cyclotron motion around a point  $\mathbf{R}_1$  or  $\mathbf{R}_2$  in the 2D plane as long as the cyclotron radius is the same. However, the electrostatic potential  $V(\mathbf{r})$  breaks this translation invariance and

In the case where the electrostatic potential varies smoothly on a length scale set by the magnetic length and does not generate LL mixing, i.e. when  $|\nabla V| \ll \hbar \omega_C/l_B$ , we may approximate the argument  $\mathbf{r}$  in the potential (3.1) by

<span id="page-44-5"></span> $V(\mathbf{r}) \simeq V(\mathbf{R}).$ 

<span id="page-44-2"></span>Notice that this approximation may seem unappropriate when we consider the confinement potential in the y-direction which may vary abruptly when ap- $\frac{1}{N}$  attrally, the system is also confined in the x-direction, but since we consider a sample with  $L \gg W$ , the system appears as translation-invariant in the x-direction when one considers intermediate length scales. The latter may be taken into account with the help of periodic boundary conditions that discretise the wave vector in the x-direction, as we have seen in the preceding chapter within the quantum-mechanical treatment of the 2D electron in the Landau

<span id="page-44-4"></span><sup>2</sup>This approximation may be viewed as the first term of an expansion of the electrostatic potential in the coherent (or vortex) state basis, where the states are maximally localised

(3.2)

thus lifts the degeneracy associated with the guiding centre.

the guiding-centre variable  $\mathbf{R},^2$ 

around the guiding-centre position  $\mathbf{R}$  [33].

gauge (see Sec. 2.4.2).

![](images/_page_45_Picture_0.jpeg)

<span id="page-45-1"></span>In the bulk, the potential landscape is created by the charged impurities in the sample, and the electrons turn clockwise on an equipotential line around a summit that is caused by a negatively charged impurity and counter-clockwise around a valley created by a positively charged impurity. If the equipotential lines are closed, as it is the case for most of the equipotential lines in a potential landscape,<sup>3</sup> an electron cannot move from one point to another one over a macroscopic distance, e.g. from one contact to the other one. An electron moving on a closed equipotential line can therefore not contribute to the electronic transport, and the electron is thus localised. Notice that this type of localisation it different from other popular types. Anderson localisation in 2D, e.g., is due to quantum interferences of the electronic wave functions [34]. Here, however, the localisation is a purely classical effect. The high-field localisation is also <sup>3</sup>In order to illustrate this point, consider a hiking tour in the mountains, e.g. around Les Houches in the French Alps. To go from one point to another one at the same height, one usual needs go downhill as well as uphill. It is very rare to be able to stay on the same height unless one wants to turn in circles that are just the closed countour lines which correspond to closed equipotential lines in our potential landscape. For those who participated at the Les Houches session which was outsourced to Singapore, where there are no mountains and where the whether is anyway too hot for hiking, just look at a hiking map of some mountainous region. Then search for countour lines that connect one border of the map to the opposite border. It turns out to be very hard to find such lines as compared to a large number of closed

<span id="page-45-0"></span>countour lines.

![](images/_page_46_Picture_0.jpeg)

<span id="page-46-0"></span>Remember that for a fixed wave vector k in the x-direction, the position around which the one-dimensional harmonic oscillator is centred is fixed by Eq. (2.56),  $y_0 = kl_B^2$ . We may therefore expand the confinement potential, even in the case

<span id="page-46-2"></span> $V(y) \simeq V(y_0 = kl_B^2) - eE(y_0)(y - y_0) + \mathcal{O}\left(\frac{\partial^2 V}{\partial u^2}\right),$ 

where the local electric field is given in terms of the first derivative of the

 $eE(y_0) = -\left. \frac{\partial V_{\text{conf}}}{\partial y} \right|_{y_0}.$ 

 $H = \frac{p_y^2}{2m} + \frac{1}{2}m\omega_C(y - y_0')^2 + V_{\text{conf}}(y_0) - \frac{1}{2}mv_D^2(y_0),$ 

<span id="page-46-1"></span><sup>4</sup>In the semi-classical picture the extended states are also called *skipping orbits*.

of a strong variation, around this position,

This expansion yields the Hamiltonian

potential at  $y_0$ ,

where the local drift velocity reads  $v_D = E(y_0)/B$  and the position of the harmonic oscillator is shifted,  $y_0 \to y_0' = y_0 + eE(y_0)/m\omega_C^2$ . Notice that the last term is quadratic in the electric field  $E(y_0)$  and therefore a second-order term in the expansion of the confinement potential. We neglect this term in the following calculations. The final Hamiltonian then reads

$$H = \frac{p_y^2}{2m} + \frac{1}{2}m\omega_C(y - y_0')^2 + V_{\text{conf}}(y_0'), \tag{3.7}$$

where we have replaced the argument  $y_0$  by the shifted harmonic-oscillator position  $y'_0$ , which is valid at first order in the expansion of the confinement potential. One therefore obtains the energy spectrum

<span id="page-47-1"></span>
$$\epsilon_{n,y_0} = \hbar\omega_C \left( n + \frac{1}{2} \right) + V(y_0), \tag{3.8}$$

where we have omitted the prime at the shifted harmonic-oscillator position to simplify the notation. One therefore obtains the same LL spectrum as in the absence of a confinement potential, apart from an energy shift that is determined by the value of the confinement potential at the harmonic-oscillator position, which may indeed vary strongly. This position  $y_0$  plays the role of the guiding-centre position, as we have already mentioned in the last chapter, where we have calculated the electronic wave functions in the Landau gauge (2.4.2). One thus obtains a result that is consistent with the semi-classical treatment presented above.

## <span id="page-47-0"></span>3.2 Conductance of a Single Landau Level

We now calculate the conductance of a completely filled LL for the geometry depicted in Fig. 3.1, i.e. when all quantum states (described within the Landau gauge) of the *n*-th LL are occupied. In a first step, we calculate the current of the *n*-th LL, which flows from the left to the right contact, with the help of the formula [35]

<span id="page-47-3"></span>
$$I_n^x = -\frac{e}{L} \sum_k \langle n, k | v_x | n, k \rangle, \tag{3.9}$$

i.e. as the sum over all  $N_B$  quantum channels labelled by the wave vector  $k = 2\pi m/L$ , with the velocity

$$\langle n, k | v_x | n, k \rangle = \frac{1}{\hbar} \frac{\partial \epsilon_{n,k}}{\partial k} = \frac{L}{2\pi\hbar} \frac{\Delta \epsilon_{n,m}}{\Delta m},$$

in terms of the dispersion relation (3.8).<sup>5</sup> Notice that the velocity in the y-direction is zero because the energy does not disperse as a function of the y-

$$\dot{x} = \frac{1}{\hbar} \frac{\partial H}{\partial k},$$

which we evaluate in the state  $|n,k\rangle$ . In the last step we have used the periodic boundary conditions.

<span id="page-47-2"></span><sup>&</sup>lt;sup>5</sup>This relation may be obtained from the Heisenberg equations of motion,  $i\hbar\dot{x}=[x,H]=(\partial H/\partial p_x)[x,p_x]=i\partial H/\partial k$ , where we have used Eq. (2.10) and  $p_x=\hbar k$ . One therefore obtains the operator equation

![](images/_page_48_Figure_2.jpeg)

<span id="page-48-2"></span>Figure 3.2: Edge states. (a) The LLs are bent upwards when approaching the sample edge, which may be modeled by an increasing confinement potential. One may associate with each LL n a maximal value  $y_{max}^n$  of the y-component where the LL crosses the chemical potential  $\mu_{max}$ . (b) At each position  $y_{max}^n$ , the filling factor decreases by a jump of 1. The n-th edge state is associated with the jump at  $y_{max}^n$  and the gradient of the confinement potential imposes a direction to the Hall drift of this state (chirality). This chirality is the same for all edge states at the same edge.

component of the wave vector. The above expression is readily evaluated with  $\Delta m = 1$ , and one obtains

$$\langle n, k | v_x | n, k \rangle = \frac{L}{h} (\epsilon_{n,m+1} - \epsilon_{n,m}).$$

With the help of this expression, the current (3.9) of the n-th LL becomes

$$I_{n} = -\frac{e}{L} \sum_{m} \frac{L}{h} \left( \epsilon_{n,m+1} - \epsilon_{n,m} \right),$$

and one notices that all terms in the sum cancel apart from the boundary terms  $\epsilon_{n,m_{min}}$  and  $\epsilon_{n,m_{min}}$ , which correspond to the chemical potentials  $\mu_{min}$  and  $\mu_{max}$ , respectively. The difference between these two chemical potentials may be described in terms of the (Hall) voltage V between the upper and the lower edge,  $\mu_{max} - \mu_{min} = -eV$ . One thus obtains the final result

<span id="page-48-1"></span>
$$I_n = -\frac{e}{h} \left( \mu_{max} - \mu_{min} \right) = \frac{e^2}{h} V.$$
 (3.10)

This means that each LL contributes one quantum of conductance  $G_n = e^2/h$  to the electronic transport and n completely filled LLs contribute a conductance<sup>6</sup>

<span id="page-48-3"></span>
$$G = \sum_{n'=0}^{n-1} G_{n'} = n \frac{e^2}{h} \,. \tag{3.11}$$

<span id="page-48-0"></span><sup>&</sup>lt;sup>6</sup>Notice that, because the lowest LL is labelled by n' = 0, the last one has the index n - 1 in the case of n completely filled levels.

Notice furthermore that this is a particular example of the Landauer-B¨uttiker formula of quantum transport

$$G_n = \frac{e^2}{h} T_n$$

through a conduction channel n, where T<sup>n</sup> is the transmission coefficient of the channel \[36, 35, [37\]](#page-116-3). Because T<sup>n</sup> + R<sup>n</sup> = 1, in terms of the reflexion coefficient, the above result \(3.10\) indicates that each filled LL may be viewed as a conduction channel with perfect transmission T<sup>n</sup> = 1, i.e. where an injected electron is not reflected or backscattered.

#### <span id="page-49-0"></span>3.2.1 Edge states

The astonishing feature of perfect transmission, which is independent of the length L (or more precisely of the aspect ratio L/W, see the discussion in Sec. 1.1.2 of the introduction) or the particular geometry of the sample, may be understood from the edge-state picture which we have introduced above (see Fig. 3.2\). Consider the upper edge, without loss of generality. The currenttransporting edge state of the n-th LL is the one situated at y n max, where the n-th LL crosses the Fermi energy and where the filling factor jumps from ν = n+1 to n. 7 Due to the upward bent of the confinement potential a particular direction is imposed on the electronic motion, which is nothing other than the Hall drift (see Fig. 3.1\). This uni-directional motion is also called chirality of the edge state. Notice that this is the same chirality which one expects from the semi-classical expression \(3.5\) for the drift velocity. The chirality is the same for all edge states n at the same sample edge where the gradient of the confinement potential does not change its direction. Therefore, even if an electron is scattered from one channel n to another one n ′ at the same edge it does not change its direction of motion, and the electron cannot be backscattered unless it is scattered to the opposite edge with inverse chirality. However, in a usual quantum Hall system, the opposite edges are separated by a macroscopic distance ∼ W, and backscattering processes are therefore strongly (exponentially) suppressed in the ratio lB/W between the magnetic length, which determines the spatial extension of quantum-mechanical state, and the macroscopic sample width W. Notice that the quantum Hall system at integer filling factors ν = n is therefore a very unusual electron liquid: it is indeed a bulk insulator with perfectly conducting (non-dissipative) edges.

<span id="page-49-1"></span><sup>7</sup>Strictly speaking the filling factor does not jump not abruptly when one takes interactions between the electrons into account. In this case, two incompressible strips, of ν = n + 1 and ν = n are separated by a compressible strip of finite width. The picture of chiral electron transport remains, however, essentially the same when considering such compressible regions.

![](images/_page_50_Picture_2.jpeg)

Figure 3.3: Two-terminal measurement. The current is driven through the sample via the left and the right contacts, where one also measures the voltage drop and thus a resistance. The upper edge is in thermodynamic equilibrium with the left contact (blue), whereas the lower one is in equilibrium with the right contact (red). The chemical potential drops abruptly when the upper edge reaches the right contact, and when the lower edge reaches the left contact. Dissipation occurs in these hot spots (red dots). The measured resistance between the two contacts thus equals the Hall resistance.

# <span id="page-50-2"></span><span id="page-50-0"></span>3.3 Two-terminal versus Six-Terminal Measurement

#### <span id="page-50-1"></span>3.3.1 Two-terminal measurement

In the preceding section Sec. (3.2), we have calculated the conductance of a single LL (and n filled LLs) within a so-called two-terminal measurement, where we inject a current in the left contact with chemical potential  $\mu_L$  and collect the outcoming current at the right contact with  $\mu_R$ . As a consequence of Eq. (3.10), this current builds up a voltage V between the upper and the lower sample edge. This voltage drop is therefore associated with a Hall resistance, which is the inverse of the conductance  $G = ne^2/h$ ,

<span id="page-50-3"></span>
$$R_H = G^{-1} = \frac{h}{e^2} \frac{1}{n} , \qquad (3.12)$$

and which coincides with the contact (or interface) resistance of a mesoscopic system [37]. However, the voltage drop  $V_L$  between the left and the right contact is given by the difference of the chemical potentials in the contacts,  $\mu_R - \mu_L = -eV_L$ , and the associated longitudinal resistance  $V_L/I$  is non-zero, in contrast to what we have seen in the introduction. This is due to the fact that the

![](images/_page_51_Picture_1.jpeg)

52

edge is in thermodynamic equilibrium with the left contact and the chemical potentials therefore coincide,  $\mu_L = \mu_{max}$  (see Fig.3.3). Now, when the upper edge touches the right contact which is at a different chemical potential  $\mu_R$ , the chemical potential of the upper edge must rapidly relax to be in equilibrium

with the right contact. In the same manner, the lower edge is in equilibrium

with the right contact,  $\mu_{\min} = \mu_R$ , and abruptly changes when touching the left contact. The rapid change in the chemical potential is associated with a dissipation of energy (at so-called *hot spots*) that has been observed experimentally [38]. In this experiment, the sample was put in liquid helium and the heating at the hot spots caused a local vaporisation of the helium observable in form of

at the hot spots caused a local vaporisation of the helium observable in form of a fountain of gas bubbles.

Due to the equivalence of the chemical potentials  $\mu_L = \mu_{max}$  and  $\mu_{min} = \mu_R$ , the voltage drops V, between the upper and the lower edge, and  $V_L$  between the current contacts are equal,  $V = V_L$ . An unexpected consequence of this equation is that in a resistance measurement between the two contacts, in the two-terminal configuration, the two-terminal resistance equals the Hall resistance,

tance,  $R_{R-L}=R_H=\frac{h}{e^2}\frac{1}{n}\;, \tag{3.13}$  and not the (vanishing) longitudinal resistance, when the bulk is insulating (at  $\nu=n$ ).

<span id="page-51-0"></span>3.3.2 Six-terminal measurement

A more sophisticated geometry that allows for the simulaneous measurement of a well-defined longitudinal and Hall resistance is the six-terminal geometry, with two additional contacts at the upper and two at the lower edge [see Fig. 3.4(a)]. These additional contacts (2 and 3 at the upper and 5 and 6 at the lower

3.4(a)]. These additional contacts (2 and 3 at the upper and 5 and 6 at the lower edge, the left and the right contacts being labelled by 1 and 4, respectively) are used to measure a voltage, i.e. they have ideally an infinitely high internal resistance to prevent electrons to leak out of or into the sample. The chemical potential therefore remains constant at the upper edge  $\mu_L = \mu_2 = \mu_3$ , as well as that at the lower edge  $\mu_R = \mu_5 = \mu_6$ , and one measures a zero-resistance,

of the conductance through n LLs (see Sec. 3.11), which is entirely transverse. The conductance matrix is thus off-diagonal, as well as the resistance matrix,  $G = \begin{pmatrix} 0 & n\frac{e^2}{h} \\ -n\frac{e^2}{h} & 0 \end{pmatrix} \quad \text{and} \quad R = \begin{pmatrix} 0 & -\frac{h}{e^2}\frac{1}{n} \\ \frac{h}{e^2}\frac{1}{n} & 0 \end{pmatrix}, \quad (3.14)$ 

<span id="page-51-1"></span> $R_L = (\mu_2 - \mu_3)/eI = (\mu_5 - \mu_6)/eI = 0$ , as one expects from the calculation

![](images/_page_52_Picture_0.jpeg)

<span id="page-52-0"></span>not leak out or in at the contacts 2 and 3, where one measures the longitudinal resistance. In the same manner, the chemical potential  $\mu_R$  (red) remains constant between the contacts 5 and 6 on the lower edge. The longitudinal resistance measured between 2 and 3 as well as between 5 and 6 is therefore  $R_L = (\mu_2 - \mu_3)/eI = (\mu_5 - \mu_6)/eI = 0$ . The Hall resistance is determined by the potential difference between the two edges and thus measured, e.g. between the contacts 5 and 3, where  $\mu_5 - \mu_3 = \mu_R - \mu_L$ , and thus  $R_H = (\mu_3 - \mu_5)/eI$ . (b) Four-terminal measurement in the van-der-Pauw geometry. In a Hall-resistance measurement, one drives a current through the sample via the contacts 1 and 3 (connected by the continuous blue line) and measures the Hall resistance via the contacts 2 and 4 (dashed blue line). In a measurement of the longitudinal resistance, the current is driven through the sample via the contacts 1 and 4 (continuous red line) and one measures a resistance between the contacts 2 and

3 (connected by the dashed red line).

![](images/_page_53_Picture_0.jpeg)

the geometry in which the contacts are placed at the sample \[39, [35\]](#page-116-1). This aspect is often not sufficiently appreciated in the literature, namely the fact that one measures, in a two-terminal geometry, a Hall resistance between the contacts that are used to inject and collect the current and not a longitudinal resistance, as one may have expected naively, when the system is in the IQHE

3.4 The Integer Quantum Hall Effect and Per-

Until now we have shown that the Hall resistance is quantised Eq. [\(3.12\)] when n LLs are completely filled, i.e. when the filling factor is exactly ν = n. However, we have not yet explained the occurence of plateaus in the Hall resistance, i.e. a Hall resistance that remains constant even if one varies the filling factor,

<span id="page-53-1"></span><sup>8</sup>Strictly speaking, we have not gained anything because the quantum treatment allows us only to determine the Hall resistance at certain points of the Hall curve, those at the magnetic

8

In order to explain the

<span id="page-53-0"></span>condition.

colation

e.g. by sweeping the magnetic field, around ν = n.

![](images/_page_54_Figure_2.jpeg)

<span id="page-54-0"></span>Figure 3.5: Quantum Hall effect. The (impurity-broadened) density of states is shown in the first line for increasing fillings (a) - (c) described by the Fermi energy  $E_F$ . The second line represents the impurity-potential landscape the valleys of which become successively filled with electrons when increasing the filling factor, i.e. when lowering the magnetic field at fixed particle number. The third line shows the corresponding Hall (blue) and the longitudinal (red) resistance measured in a six-terminal geometry, as a function of the magnetic field. The first figure in column (c) indicates that the bulk extended states are in the centre of the DOS peaks, whereas the localised states are in the tails.

constance of the Hall resistance over a rather large interval of magnetic field around ν = n, we need to take into account the semi-classical localisation of additional electrons (or holes) described in Sec. 3.1. This is shown in Fig. 3.5, where we represent the filling of the LLs (first line), the potential landscape of the last partially-filled level (second line) and the resistances as a function of the magnetic field, measured in a six-terminal geometry (third line). We start with the situation of n completely filled LLs [column (a) of Fig. [3.5\]](#page-54-0), which we have extensively discussed above: the LL n (and its potential landscape) is unoccupied.9 In a six-terminal measurement, one therfore measures the Hall resistance R<sup>H</sup> = h/e<sup>2</sup>n and a zero longitudinal resistance, as we have seen in Eq. \(3.14\).

In column (b) of Fig. 3.5, we represent the situation where the LL n gets moderately filled by electrons when the magnetic field B is decreased. These electrons in n populate preferentially the valleys of the potential landscape, or more precisely the closed equipotential lines that enclose these valleys. The electrons in the LL n are thus (classically) localised somewhere in the bulk and do not affect the global transport characteristics, measured by the resistances, because they are not probed by the sample contacts. Therefore, the Hall resistance remains unaltered and the longitudinal resistance remains zero despite the change of the magnetic field. This is the origin of the plateau in the Hall resistance.

If one continues to lower the magnetic field, the regions of the potential landscape in the LL n occupied by electrons become larger, and they are eventually enclosed by equipotential lines that pass through the bulk and that connect the opposite edges. In this case, an electron injected at the left contact and travelling a certain distance at the upper edge may jump into the state associated with this equipotential line and thus reach the lower edge. Due to its chirality, the electron is then backscattered to the left contact, which causes an increase in the longitudinal resistance. Indeed, if one measures the resistance between the two contacts at the lower edge, a potential drop is caused by the electron that leaks in from this equipotential connecting the upper and the lower edge. It is this potential drop that causes a non-zero longitudinal resistance. At the same moment the Hall resistance is no longer quantised and jumps to the next (lower) plateau, a situation that is called plateau transition. This situation of electron-filled equipotential lines connecting opposite edges, which are thus extended states see first line of Fig. [3.5\(c)] as opposed to the bulk localised states, arises when the LL n is approximately half-filled. Notice that these extended states, which are found in the centre of the DOS peaks see upper part of Fig. [3.5\(c)], are bulk states in contrast to the above-mentioned edge states, which are naturally also extended

The clean jump in the Hall resistance at the plateau transition accompanied

fields corresponding to ν = hnel/eB = n. If we substitute the filling factor in Eq. \(3.12\), we see immediately that <sup>R</sup><sup>H</sup> <sup>=</sup> h/e2<sup>ν</sup> <sup>=</sup> B/enel, i.e. one retrieves the classical result for the Hall resistance.

<span id="page-55-0"></span><sup>9</sup>Remember that due to the label 0 for the lowest LL, all LLs with n ′ = 0, ...,n − 1 are the completely filled and the LL n is then the lowest unoccupied level.

![](images/_page_56_Figure_2.jpeg)

<span id="page-56-1"></span>Figure 3.6: STS measurements by Hashimoto et al., 2008, on a 2D electron system on a n-InSb surface. The figures (a) - (g) show the local DOS at various sample voltages, around the peak obtained from a dI/dV measurement (h). Figure (i) shows a calculated characteristic LDOS, and figure (j) an STS result on a larger scale.

by a peak in the longitudinal one is only visible in the six- (or four-)terminal measurement. As we have argued in Sec. 3.3.2, there is no clear cut between the longitudinal and the Hall resistivity in the two-terminal configuration, where the resistance measured between the current contacts is indeed quantised in the IQHE. At the plateau transition, however, the chemical potential at the edges is no longer constant because of backscattered electrons and the resistance is no longer quantised. One observes indeed the resistance peak associated with the longitudinal resistance in the six- or four-terminal configuration. As a consequence, one measures, at the plateau transition, the superposition of the Hall and the longitudinal resistances.

If one increases even more the filling of the LL n, the same arguments apply but now in terms of hole states. The Hall resistance is quantised as R<sup>H</sup> = h/e<sup>2</sup> (n + 1), and the holes (i.e. the lacking electrons with respect to n + 1 completely filled LLs) get localised in states at closed equipotential lines around the potential summits. As a consequence, the longitudinal resistance drops to zero again.

#### <span id="page-56-0"></span>3.4.1 Extended and localised bulk states in an optical measurement

The physical picture presented above, in terms of localised and extended bulk states, has recently been confirmed in scanning-tunneling spectroscopy (STS) of a 2D electron system that was prepared on an n-InSb surface instead of the more common GaAs/AlGaAs heterostructure [\[40\]](#page-116-6). Its advantage consists of its accessibility by an "optical" (surface) measurement that cannot be performed if the 2D electron gas is buried deep in a semiconductor heterostructure. In an STS measurement one scans the sample and thus measures the local density of states at a certain energy that can be tuned via the voltage between the tip of the electron microscope and the sample. When measuring the differential conductance dI/dV , which is proportional to the DOS, one observes a peak that corresponds to the centre of a LL Fig. [3.6\(h)] where the extended states are capable of transporting a current between the different electric contacts, as mentioned above. Whereas the quantum states at energies corresponding to closed equipotential lines of the impurity landscape are clearly visible as closed orbits in Fig. 3.6\(a),(b) and (f),(g), the states in the vicinity of the peak are more and more extended, as shown by the spaghetti-like lines in Figs. 3.6\(c),(d) and (e), as one would expect from the arguments presented above.

#### <span id="page-57-0"></span>3.4.2 Plateau transitions and scaling laws

The physical picture presented above suggests that the plateau transition in the Hall resistance is related to a percolation transition, where initially separated electron-filled valleys start to percolate between the opposite sample edges beyond a certain threshold of the filling. Because of the second-order character of a percolation transition, this scenario suggests that the plateau transition is a second-order quantum phase transition described by universal scaling laws, where the control parameter is just the magnetic field B \[41, [42\]](#page-116-8). We finish this chapter on the IQHE with a brief overview over these scaling laws, and refer the interested reader to the literature \[41, [42\]](#page-116-8) and the class given by G. Batrouni at the same Singapore session of Les Houches Summer School 2009. 10

The phase transition occurs at the critical magnetic field B<sup>c</sup> and is characterised by an algebraically diverging correlation length

$$\xi \sim \left| B - B_c \right|^{-\nu},\tag{3.15}$$

where ν is called the critical exponent. 11 In the same manner, the temporal fluctuations are described by a correlation "length" ξ<sup>τ</sup> that is related to the spatial correlation length ξ,

$$\xi_{\tau} \sim \xi^{z} \sim \left| B - B_{c} \right|^{-z\nu}, \tag{3.16}$$

where z is called dynamical critical exponent. It is roughly a measure of the anisotropy between the spatial and temporal fluctuations, which is often encountered in non-relativistic condensed-matter systems.12

At the phase transition Bc, the longitudinal and transverse resistivities ρL/H are described in terms of universal functions that are functions of the ratio τ/ξ<sup>τ</sup>

<span id="page-57-1"></span><sup>10</sup>The lecture notes for this class are availabel on the School's program webpage: <http://www.ntu.edu.sg/ias/upcomingevents/LHSOPS09/Pages/programme.aspx>

<sup>11</sup>Although we use the same Greek letter ν for the critical exponent, it must not be confunded with the filling factor, which plays no role in this subsection.

<span id="page-57-3"></span><span id="page-57-2"></span><sup>12</sup>Notice that in relativity, time is considered as the "fourth" dimension, and Lorentz invariance would require that spatial and temporal fluctuations be equivalent, i.e. z = 1.

![](images/_page_58_Figure_2.jpeg)

<span id="page-58-1"></span>Figure 3.7: Experiment by Wei *et al.*, 1988. The width of the transition  $\Delta B$  and of the derivative of the Hall resisitivity  $\partial \rho_{xy}/\partial B$ , measured as a function of temperature, reveals a scaling law with an exponent  $1/z\nu = 0.42 \pm 0.04$ , for the transition between the filling factors  $1 \to 2$   $(N = 0 \downarrow)$ ,  $2 \to 3$   $(N = 1 \uparrow)$  and  $3 \to 4$   $(N = 1 \downarrow)$ .

between the (imaginary) time  $\tau$ , which is proportional to the inverse temperature,  $\hbar/\tau = k_B T$  [41, 42] and the temporal correlation length  $\xi_{\tau}$ ,

<span id="page-58-0"></span>
$$\rho_{L/H} = f_{L/H} \left( \frac{\tau}{\xi_{\tau}} \right) = f_{L/H} \left( \frac{\Delta B^{z\nu}}{T} \right), \tag{3.17}$$

where we have defined  $\Delta B \equiv |B - B_c|$ . In the case of an AC (alternating current) measurement at frequency  $\omega$ , another dimensionless quantity, namely the ratio between the frequency and the temperature,  $\hbar \omega / k_B T$ , needs to be taken into account such that the universal function reads

$$\rho_{L/H}^{AC} = f_{L/H} \left( \frac{\tau}{\xi_{\tau}}, \frac{\hbar \omega}{k_B T} \right).$$

However, we do not consider an alternating current here. Equation (3.17) then yields the scaling of the width of the peak in the longitudinal resistance (or else the plateau transition)

$$\Delta B \sim T^{1/z\nu}.\tag{3.18}$$

A measurement of this width by Wei et al. [43] has confirmed such critical behaviour with an exponent  $1/z\nu = 0.42 \pm 0.04$  (see Fig. 3.7).

Furthermore, one may distinguish between the two exponents  $\nu$  and z within a measurement of the plateau-transition width as a function of the electric field

agreement with the experimental data [43, 44].

<span id="page-59-2"></span><span id="page-59-1"></span>one interchanges negatively and positively charged impurities.

account [50].

<span id="page-59-0"></span>3.5

effect has been proposed by Chalker and Coddington [47], though with simplifying assumptions for the puddle geometry, <sup>13</sup> and one obtains a critical exponent  $\nu = 2.5 \pm 0.5$  from numerical studies of this model [47, 48], in quite a good

In spite of the good agreement with experimental findings, these theoretical results need to be handled with care – indeed, analytical calculations have shown that the dynamical exponent should be exactly z=2 for non-interacting electrons, whereas the measured value  $z\simeq 1$  is obtained when interactions are taken into account on the level of the Hartree-Fock approximation [49]. Furtherrmore, very recent numerical calculations within the Chalker-Coddington model have shown that the accurate value of the critical exponent is slightly larger ( $\nu \simeq 2.59$ ) than the measured one when interactions are not taken into

Relativistic Quantum Hall Effect in Graphene

We finish this chapter on the IQHE with a short presentation of the relativistic quantum Hall effect (RQHE) in graphene, which is understandable in the same framework of LL quantisation and (semi-classical) one-particle localisation as the IQHE in a non-relativistic 2D electron system. Indeed, the above arguments also apply to relativistic electrons in graphene, but we need to take into account the two different carrier types, electrons and holes, which carry a different charge. This is not so much a problem in the case of the impurity potential with its valleys and summits: in a particle-hole transformation, a valley becomes a summit and vice versa. Furthermore, the direction of the Hall drift all length scales, the results are expected to be independent on these microscopic assumptions.

![](images/_page_60_Picture_0.jpeg)

changes in this transformation. Because of the universality of the quantum Hall effect, both types of impurity distributions related by particle-hole symmetry yield the same quantisation of the Hall resistance. The picture of semi-classical localisation therefore applies also in the case of relativistic electrons in graphene. The situation is different for the confinement potential. An ansatz of the form  $V(y)\mathbbm{1}$  – remember that the Hamiltonian of electrons in relativistic graphene is a 2 × 2 matrix that reflects the two different sublattices A and B – has the problem that an increase  $V(y-y_{max/min})\to\infty$  at the sample edge confines electrons but not the holes of the valence band for which we would need  $V(y-y_{max/min})\to-\infty$  for an efficient confinement. A possible confinement

<span id="page-60-0"></span> $V_{\text{conf}}(y) = V(y) \sigma^z = \begin{pmatrix} V(y) & 0 \\ 0 & -V(y) \end{pmatrix},$ 

which, together with the Hamiltonian (2.8), yields the Hamiltonian which corresponds to the non-relativistic model (3.6). For a constant term M = V(y) the contribution (3.20) plays the role of a mass of a relativistic particle (see also Appendix B). Therefore, the confinement (3.20) is sometimes also called mass confinement. The corresponding energy spectrum, which one obtains within the same approximation as in Sec. 3.1 via the replacement  $y \to y_0 = kl_B^2$  in the

(3.20)

potential may be formed with the Pauli matrix  $\sigma^z$ ,

<span id="page-60-1"></span>half-filled.

<span id="page-61-0"></span>![](images/_page_61_Picture_0.jpeg)

yields a qualitatively correct picture, the fine structure of the dispersion at the edge depends on the edge geometry [51]. For further reading, we refer the

With the help of these preliminary considerations, we are now prepared to understand the RQHE in graphene – the semi-classical localisation is the same as in the non-relativistic case, and the confinement, which needed to be adopted to account for the simultaneous presence of electron- and hole-like LLs, yields the edge states which are responsible for the quantum transport and, thus, the resistance quantisation. The RQHE was indeed discovered in 2005 by two different groups [6, 7], and the results are shown in Fig. 3.9 [7]. The phenomenology of the RQHE is the same as that of the IQHE in non-relativistic LLs: one observes plateaus in the Hall resistance while the longitudinal resistance vanishes. Notice that one may vary the filling factor either by changing the B-field at fixed carrier density [Fig. 3.9(a)] or one keeps the B-field fixed while changing the carrier density with the help of a gate voltage [Fig. 3.9(c)]. The latter measurement is much easier to perform in graphene than in non-relativistic 2D

In spite of the similarity with the non-relativistic IQHE, one notices, in Fig. 3.9, an essential difference: the quantum Hall effect is observed at the filling

interested reader to the literature [21].

electron gases in semiconductor heterostructures.

![](images/_page_62_Figure_2.jpeg)

<span id="page-62-0"></span>Figure 3.9: Measurement of the relativistic quantum Hall effect (Zhang et al., 2005). (a) RQHE at fixed carrier density (V<sup>G</sup> = 15 V) at T = 30 mK. The filling factor is varied by sweeping the magnetic field. (b) Sketch of the DOS with the Fermi energy between the LLs n = 0 and +, n = 1. (c) RQHE at fixed magnetic field (B = 9 T) at higher temperatures, T = 1.6 K. The filling factor is now varied by changing the gate voltage.

factors

<span id="page-63-0"></span>
$$\nu = \pm 2(2n+1),\tag{3.22}$$

in terms of the LL quantum number n, whereas the IQHE is observed at ν = n (or ν = 2n if the LLs are spin-degenerate). The step in units of 4 is easy to understand: each relativistic LL in graphene is four-fold degenerate (in addition to the guiding-centre degeneracy), due to the two-fold spin and the additional two-fold valley degeneracy. However, there is an "offset" of 2. This is due to the fact that the filling factor ν = 0 corresponds to no carriers in the system, i.e. to a situation where the Fermi energy is exactly at the Dirac point (undoped graphene). In this case, one has a perfect electron-hole symmetry, and the n = 0 LL must therefore be half-filled see Fig. [3.8\(b)], or else: there are as many electrons as holes in n = 0. According to the considerations presented in Sec. 3.4, this does not correspond to a situation where one observes a quantum Hall effect due to percolating extended states. Indeed, the system turns out to be metallic at ν = 0 with a finite non-zero longitudinal resistance \[6, [7\]](#page-114-6). A situation, where one would expect a quantum Hall effect, arises when the central LL n = 0 is completely filled (or completely empty). As a consequence of the four-fold level degeneracy, one obtains the quantum Hall effect at ν = 2 (or ν = −2) observed in the experiments (see Fig. 3.9\). This is the origin of the particular filling-factor sequence \(3.22\) of the RQHE in graphene.

## <span id="page-64-0"></span>Chapter 4

# Strong Correlations and the Fractional Quantum Hall Effect

In the preceding chapter, we have seen that one may understand the essential featues of the IQHE within a one-particle picture, i.e. in terms of Landau quantisation; at integer filling factors  $\nu = n$ , which correspond to n completely filled LLs, an additional electron is forced, as a result of the Pauli principle, to populate the next higher (unoccupied) LL [see Fig. 4.1(a)]. It therefore, needs to "pay" a finite amount of energy  $\hbar\omega_C$  [or  $\sqrt{2}(\hbar v/l_B)(\sqrt{n}-\sqrt{n-1})$  in the case of the RQHE in graphene and is localised by the impurities in the sample, due to the classical Hall drift which forces the electron to move on closed equipotential lines. The system is said to be incompressible because one may not vary the filling factor and pay only an infinitesimal amount of energy indeed in the case of a fixed particle number, consider an infinitesimal decrease of the magnetic field which amounts to an infinitesimal change of the surface  $2\pi l_B^2$  occupied by each quantum state. Since the total surface of the system remains constant, the infinitesimal increase of  $2\pi l_B^2$  may not be accommodated by an infinitesimal change in energy, due to the gap between the LL n-1 and n where at least one electron must be promoted to. This gives rise to a zero compressibility.

In view of this picture of the quantum Hall effect, it was therefore a big surprise to observe a FQHE at a filling factor  $\nu=1/3$ , with the corresponding Hall quantisation  $R_H=h/e^2\nu=3h/e^2$  [13], and, later, at a large set of other fractional filling factors. Indeed, if only the kinetic energy is taken into account, the ground state at  $\nu=1/3$  is highly degenerate and there is no evident gap present in the system: the Pauli principle no longer prevents an additional electron to populate the next higher LL, but it finds enough place in the lowest

<span id="page-64-1"></span><sup>&</sup>lt;sup>1</sup>As before, we neglect the electron spin to render the discussion as simple as possible. The role of spin will be discussed briefly in the last chapter on multi-component systems.

![](images/_page_65_Picture_2.jpeg)

Figure 4.1: (a) Sketch of a completely occupied LL. An additional electron (grey circle) is forced to populate the next higher LL because of the Pauli principle. (b) Sketch of a partially filled LL. Because of the presence of unoccupied states in the LL (crosses), the Pauli principle does not prevent an additional electron (grey circle) to populate the next higher LL. The low-energy dynamical properties of the electrons are described by excitations within the same LL (no cost in kinetic energy), and inter-LL excitations are now part of the high-energy degrees of freedom.

#### <span id="page-65-1"></span>LL which is only one-third filled.

Notice that we have neglected so far the mutual Coulomb repulsion between the electrons, which happens to be responsible for the occurence of the FHQE. The relevance of electronic interactions is discussed in the next section (Sec. 4.1\). In Sec. 4.2, we present the basic results of Laughlin's theory of the FQHE, such as the ground-state wave functions, fractionally charged quasiparticles and the interpretation of Laughlin's wave function in terms of a 2D one-component plasma. The related issue of fractional statistics is introduced in a section apart (Sec. 4.3\), and we close this chapter with a short discussion of different generalisations of Laughlin's wave function, such as CF theory or the Moore-Read wave function in half-filled LLs.

## <span id="page-65-0"></span>4.1 The Role of Coulomb Interactions

As already mentioned above, the situation of a partially filled LL is somewhat opposite to that of n completely occupied levels, where one observes the IQHE. This difference is summarised in Fig. 4.1 and it is also the origin of the different role played by the Coulomb repulsion between the electrons. In the case of n completely filled LLs, one has a non-degenerate (Fermi-liquid-like) ground state, where the interactions may be treated within a perturbative approach. Indeed, any type of excitation involves a transition between two adjacent LLs that are separated by an energy gap of ¯hω<sup>C</sup> see Fig. [4.1\(a)],2 and we need to compare the Coulomb energy at the characteristic length scale R<sup>C</sup> = l<sup>B</sup> √ 2n + 1 to this gap,

$$\frac{V_C}{\hbar\omega_C} \sim \frac{me^{3/2}}{\epsilon\hbar^{3/2}} (Bn)^{-1/2},$$

<span id="page-65-2"></span><sup>2</sup> In order to simplify the discussion, we consider only the IQHE in non-relativistic quantum Hall systems, but the arguments apply also to the RQHE in graphene.

which turns out to be nothing other than the usual dimensionless coupling constant

$$r_s = \frac{me^2}{\epsilon \hbar^2} n_{el}^{-1}$$

for the 2D Coulomb gas in Fermi liquid theory [52, 53]. The last expression is obtained by identifying the Fermi energy  $E_F = \hbar^2 k_F^2/2m$ , in terms of the Fermi wave vector  $k_F$ , with the energy of the last occupied LL  $\hbar\omega_C n$ . The perturbative approach allows one, e.g., to describe collective electronic excitations in the IQHE, such as magneto-plasmon modes (the 2D plasmon in the presence of a magnetic field) or magneto-excitons (inter-LL excitations that acquire a dispersion due to the Coulomb interaction) [54], or else the corresponding modes of the RQHE in graphene [55, 56].

In the case of a partially filled LL n the situation is inverted: for an electronic excitation, there are enough unoccupied states in the LL n for an electron of the same level to hop to. From the point of view of the kinetic energy, there is no energy cost associated with such an excitation (low-energy degrees of freedom) whereas an excitation to the next higher (unoccupied) LL costs an energy  $\hbar\omega_C$ . Inter-LL excitations may then be neglected as belonging to high-energy degrees of freedom [Fig. 4.1(b)]. Notice that all possible distributions of N electrons within the same partially filled LL n therefore have the same kinetic energy, which effectively drops out of the problem. The macroscopic degeneracy may be lifted by phenomena due to other energy scales, such as those associated with the impurities in the sample or else the electron-electron interactions. The first hypothesis (impurities) may be immediately discarded as the driving mechanism of the FQHE because, in contrast to the IQHE, the FQHE only occurs in high-quality samples with low impurity concentrations. Indeed, the hierarchy of energy scales in the FQHE may be characterised by the succession

$$\hbar\omega_C \gtrsim V_C \gg V_{imp},$$
 (4.1)

and we therefore need to consider seriously the Coulomb repulsion, which govern the low-energy electronic properties in a partially filled LL.<sup>3</sup> Notice that we thus obtain a system of *strongly-correlated* electrons for the description of which all perturbative approaches starting from the Fermi liquid are doomed to fail. The only hope one may have to describe the FQHE is then a well-educated guess of the ground state.

The most natural guess would be that the electrons in a partially filled LL behave as classical charged particles that form a crystalline state in order to minimise their mutual Coulomb repulsion. Such a state is also called Wigner crystal (WC) because it was first proposed by Wigner in 1934 [57]. A WC has indeed been thought – before the discovery of the FQHE – to be the ground state of electrons in a partially filled LL [58]. Even if the WC is the ground state at very low filling factors, as it has been shown experimentally [59], this state may

<span id="page-66-0"></span><sup>&</sup>lt;sup>3</sup>As for the IQHE, impurities play nevertheless an important role in the localisation of quasi-particles, which we need to invoke later in this chapter in order to explain the transport properties of the FQHE.

not allow for an explanation of the FQHE. Indeed, the WC is a state that breaks a continuous spatial symmetry (translation invariance) and any such state has gapless long-wave-length excitations (Goldstone modes). The Goldstone mode of the WC (as of any other crystal) is the acoustic phonon the energy of which tends to zero at zero wave vector. One may thus compress the WC by changing the occupied surface in an infinitesimal manner or else by adding an electron without changing the macroscopic surface and pay only an infinitesimal amount of energy. The ground state is therefore compressible, i.e. it is not separated by an energy gap from its single-particle excitations, a situation that is at odds with the FQHE.

## <span id="page-67-0"></span>4.2 Laughlin's Theory

As a consequence of the above-mentioned considerations on the WC, one thus needs to search for a candidate for the ground state that does not break any continuous spatial symmetry and that has an energy gap. Such a state is the incompressible quantum liquid which was proposed by Laughlin in 1983 [\[14\]](#page-115-0) the basic features of which we present in the present section. We consider, here, only the FQHE in the lowest LL (LLL), for simplicity. There are different prescriptions to generalise the associated wave functions to higher LLs, e.g. with the help of Eq. \(2.18\) (see MacDonald, 1984). Experimentally, several FQHE states have been observed in the next higher LL n = 1 although the majority of FQHE states is found in the LLL.4

#### <span id="page-67-1"></span>4.2.1 Laughlin's guess from two-particle wave functions

In order to illustrate – one cannot speak of a derivation – Laughlin's wave function, we first need to remember the one-particle wave function of the LLL and then consider the corresponding two-particle wave function. We have already seen in Sec. 2.4.1 that a one-particle wave function in the LLL is described in terms of an analytic function times a Gaussian,5

$$\psi \sim z^{m'} e^{-|z|^2/4},$$

in terms of the integer <sup>m</sup>′ = 0, ..., N<sup>B</sup> <sup>−</sup> 1, where we have absorbed now (and in the remainder of these lecture notes) the magnetic length in the definition of the complex position, z = (x − iy)/lB.

Consider, in a second step, an arbitrary two-particle wave function. This wave function must also be an analytic function of both postions z<sup>1</sup> and z<sup>2</sup> of the first and second particle, respectively, and may be a superposition of polynomials, such as e.g. of the basis states

<span id="page-67-4"></span>
$$\psi^{(2)}(z,Z) \sim Z^M z^m e^{-(|z_1|^2 + |z_2|^2)/4},$$
 (4.2)

<sup>4</sup>There is even some slight indication for a 1/5 FQHE state in the next excited LL n = 2 [\[60\]](#page-117-6).

<span id="page-67-3"></span><span id="page-67-2"></span><sup>5</sup>We neglect the numerical prefactors here that account for the normalisation of the wave functions.

where we have defined the centre of mass coordinate  $Z = (z_1 + z_2)/2$  and the relative coordinate  $z = (z_1 - z_2)$ . The quantum number m plays the role of the relative angular momentum between the two particles, and M is associated with the total angular momentum of the pair. Because of the analyticity of the LLL wave functions, m must be an integer, and the exchange of the positions  $z_1$  and  $z_2$  imposes on m to be odd because of the electrons' fermionic nature.

Laughlin's wave function [14] is a straight-forward N-particle generalisation of the two-particle wave function (4.2),

<span id="page-68-0"></span>
$$\psi_m^L(\{z_j, z_j^*\}) = \prod_{k < l} (z_k - z_l)^m e^{-\sum_j |z_j|^2/4},$$
(4.3)

where we have omitted the normalisation constants in order to simplify the notation and where all indices run from 1 to the total number of particles N. Notice that there is no dependence on the centre of mass, but only on the relative coordinates between the particle pairs. Had there been such a dependence, described by a non-zero value of the total angular momentum quantum number  $M \neq 0$ , one would have broken a continuous spatial symmetry, in which case the state would describe a compressible rather than an incompressible state required for the FQHE, as we have mentioned above. We emphasize once again that Laughlin's wave function is not based on a mathematical derivation, although we will see below that there exist some mathematical models for which it describes the exact ground state, but it is more appropriately characterised as a variational wave function.

#### Variational parameter

The variational parameter in Laughlin's wave function (4.3) is nothing other than the exponent m, with respect to which we would, in principle, need to optimised the wave function in order to approximate the true ground state of the system. Notice, however, that due to the LLL analyticity condition and fermionic statistics, the exponent is restricted to odd integers, m = 2s + 1, in terms of the integer s. Furthermore, this variational parameter turns out to be fully determined by the filling factor  $\nu$ , as we will show with the following argument.<sup>6</sup>

Consider Laughlin's wave function as a function of the position  $z_k$  of some arbitrary but fixed electron k. There are N-1 factors of the type  $(z_k-z_l)^m$ , one for each of the remaining N-1 electrons, l, occurring in the ansatz (4.3), such that the highest power of  $z_k$  is m(N-1),

$$\prod_{k < l} (z_k - z_l)^m \sim z_k^{m(N-1)}.$$

Now, remember from Sec. 2.4.1 [see Eq. (2.54)] that the highest power of the complex particle position is fixed by the number of states  $N_B$  in each LL. This

<span id="page-68-1"></span> $<sup>^6</sup>$ We are therefore confronted with the somewhat bizarre situation where we dispose of a variational wave function with no possible variation.

yields the relation

<span id="page-69-1"></span>
$$mN - \delta = N_B \tag{4.4}$$

between the number of particles N and the number of flux quanta  $N_B$  threading the system. Here,  $\delta$  is some *shift* that is on the order of unity and that plays no role in the thermodynamic limit  $N, N_B \to \infty$ .<sup>7</sup> Because the ratio between the number of particles and that of flux quanta is nothing other than the LL filling factor (2.44),  $\nu = N/N_B$ , one notices that, in the thermodynamic limit, the "variational parameter" is entirely fixed by the filling factor, i.e.

<span id="page-69-2"></span>
$$m = 2s + 1 = \frac{1}{\nu}$$
  $\Leftrightarrow$   $\nu = \frac{1}{m} = \frac{1}{2s+1},$  (4.5)

and Laughlin's wave function is therefore a candidate wave function for the ground state at the filling factors

$$\nu = 1, 1/3, 1/5, \dots$$

Remember that the odd value m=2s+1 is required by the fermionic nature of the electrons. Formally, one may though lift this restriction and generalise Laughlin's wave function to bosonic particles by choosing an even exponent 2s. Such bosonic Laughlin wave functions have been studied theoretically in the context of rotating cold Bose gases in an optical trap [61].

#### <span id="page-69-3"></span>Laughlin's wave function at $\nu = 1$

It may seem, at first sight, astonishing that also the case of a completely filled LL for  $\nu=1$  is described in terms of a Laughlin wave function with m=1 (or s=0). Indeed, the state

$$\psi(\{z_j\}) = f_N(\{z_j\}) e^{-\sum_j |z_j|^2/4}$$

would be non-degenerate and could thus be described in terms of a Slater determinant,

$$f_N(\{z_j\}) = \det \begin{pmatrix} z_1^0 & z_1^1 & \dots & z_1^{N-1} \\ z_2^0 & z_2^1 & \dots & z_2^{N-1} \\ \vdots & \vdots & & \vdots \\ z_N^0 & z_N^1 & \dots & z_N^{N-1} \end{pmatrix}, \tag{4.6}$$

where we have omitted the ubiquitous Gaussian factor  $\exp(-\sum_j |z_j|^2/4)$ . Notice that the j-th line in this determinant corresponds to all LLL states of the j-th particle described in terms of the polynomials  $z_j^m$ . The determinant takes into account all permutations of the N particles over the N particle positions,  $z_1, ..., z_N$ , and may be rewritten in a compact manner with the help of the co-called Vandermonde determinant,

<span id="page-69-4"></span>
$$f_N(\{z_j\}) = \prod_{i < j} (z_i - z_j),$$
 (4.7)

<span id="page-69-0"></span> $<sup>^7</sup>$ Notice, however, that this shift plays an important role in numerical calculations, such as exact diagonalisation, when performed on special geometries, such as on a sphere.

which is indeed nothing other than the polynimial prefactor in Laughlin's wave function (4.3) with m=1.

Until now we have obtained an N-particle wave function from some very general symmetry considerations (LLL analyticity condition, fermionic statistics, no broken continuous spatial symmetries), but we have not at all shown that it describes indeed the ground state responsible of the FQHE. In the following parts, we will therefore discuss the basic physical properties of this, for the moment rather abstract, mathematical entity. In a first step, we will discuss some energy properties of the ground state and show that Laughlin's wave function is the exact ground state of a certain class of models that are qualitatively compared to the physical one (Coulomb interaction). We will then discuss the fractionally charged quasi-particle excitations of this wave function.

#### <span id="page-70-0"></span>4.2.2 Haldane's pseudopotentials

In order to describe the energetic properties of Laughlin's wave function (4.3), we consider again the two-particle wave function (4.2). Notice that this wave function is an exact eigenstate for any central interaction potential that depends only on the relative coordinate z between particle pairs, such as it is the case for the Coulomb interaction, V = V(|z|). One may therefore decompose the interaction potential in the relative angular momentum quantum numbers m,

$$v_m \equiv \frac{\langle m, M|V|m, M\rangle}{\langle m, M|m, M\rangle},\tag{4.8}$$

where the denominator takes into account the fact that we have not properly normalised the two-particle wave functions (4.2),  $\psi^{(2)}(z,Z) = \langle z,Z|m,M\rangle$ . The fact that there is no dependence on M is a direct consequence of the assumption that we deal with a central interaction potential, i.e.  $\langle z,Z|V|z',Z'\rangle = V(|z|)\delta_{z,z'}\delta_{Z,Z'}$ . Furthermore, there are no off-diagonal terms of the form  $\langle m,M|V|m',M\rangle$ , with  $m'\neq m$ , as one may show explicitly in the polar representation  $z=\rho\exp(i\phi)$ ,

$$\langle m, M|V|m', M\rangle \propto \int_0^{2\pi} d\phi \int_0^{\infty} d\rho \, \rho^{m+m'+1} V(\rho) e^{-i(m-m')\phi} \propto \delta_{m,m'},$$

due to the integration over the polar angle. The potentials  $v_m$  obtained from the decomposition into relative angular momentum states are also called Haldane's pseudopotentials [62]. They fully characterise the two-particle energy spectrum because the kinetic energy is the same for all two-particle states  $|m, M\rangle$ , as described above. Notice that this is a very special case: normally any repulsive interaction potential yields unbound states with a continuous energy spectrum, such as the plane-wave states in scattering theory. Here, the energy spectrum is discrete even if the interaction is repulsive, due to the presence of a quantising magnetic field. Notice further that Haldane's pseudopotentials are an image of

<span id="page-70-1"></span><sup>&</sup>lt;sup>8</sup>In order to simplify the notations, we have omitted the LL quantum number n = 0, which is the same for both particles in this wave function.

![](images/_page_71_Figure_2.jpeg)

<span id="page-71-1"></span>Figure 4.2: Haldane's pseudopotentials for the Coulomb interaction in the LLs n=0 and n=1. Notice that we have plotted the pseudopotentials for both odd and even values of the relative angular momentum m even though only odd values matter in the case of fermions.

the real-space form of the interaction potential. Indeed, if a pair of electrons is in a quantum state with relative angular momentum m, the average distance between the electrons is  $|z| \sim l_B \sqrt{2m}$ . Haldane's pseudopotential  $v_m$  is therefore roughly the value of the original interaction potential at the relative distance  $l_B \sqrt{2m}$ ,

$$v_m \simeq V\left(|z| = l_B \sqrt{2m}\right),$$
 (4.9)

and the small-m components of Haldane's pseudopotentials correspond to the short-range components of the underlying interaction potential. Figure 4.2 shows the pseudopotential expansion for the Coulomb interaction in the lowest (n=0) and the first excited (n=1) LL.

Haldane's pseudopotentials are extremely useful in the description of the N-particle state as well. Indeed, the N-particle interaction Hamiltonian V may be rewritten in terms of pseudopotentials as

$$V = \sum_{i < j} V(|z_i - z_j|) = \sum_{i < j} \sum_{m'=0}^{\infty} v_{m'} \mathcal{P}_{m'}(ij), \tag{4.10}$$

where the operator  $\mathcal{P}_{m'}(ij)$  projects the electron pair ij onto the relative angular momentum state m'. Notice that due to the factor  $\prod_{k< l} (z_k - z_l)^m$  in Laughlin's wave function (4.3), no particle pair is in a relative angular momentum state

<span id="page-71-0"></span><sup>&</sup>lt;sup>9</sup>This is similar to the average value of the radius at which the electron's guiding centre is placed in the symmetric gauge (see Sec. 2.4.1). Remember (e.g. from classical mechanics) that the decomposition of a two-particle wave function in relative and centre-of-mass coordinates maps the two-body problem to an effective one-body problem.

m' < m. If one then chooses, though somewhat artificially, all pseudopotentials with a m < m' to be positive (say 1) and all others zero,

<span id="page-72-0"></span>
$$v'_{m} = \begin{cases} 1 & \text{for } m' < m \\ 0 & \text{for } m' \ge m \end{cases}$$
 (4.11)

one obtains  $V\psi_m^L = 0$ , i.e. Laughlin's wave function is the zero-energy eigenstate of the model (4.11). Since the model describes an entirely repulsive interaction, all possible states must have an energy  $E \geq 0$ . Therefore, Laughlin's wave function is even the exact ground state of the model (4.11). Furthermore, it is the only zero-energy state because if one keeps the total number of particles and flux fixed, any other state different from that described by Laughlin's wave function involves a particle pair in a state with an angular momentum quantum number different from m. If it is smaller than m, this particle pair is affected by the associated non-zero pseudopotential m' and thus costs an energy on the order of  $v_{m'} > 0$ . If the particle pair is in a momentum state with m' > m, there is at least another pair with m'' < m in order to keep the filling factor fixed, and this pair raises the energy. These general arguments show that any excited state involves a finite (positive) energy given by a pseudopotential  $v_{m'}$ , with m' < m, which plays the role of an energy gap. In this sense, the liquid state described by Laughlin's wave function is indeed an incompressible state that already hints at the possibility of a quantum Hall effect if we can identify the correct quasi-particle of this N-particle state that becomes localised by the sample impurities.

Notice that the above considerations are based on an extremely artificial model interaction (4.11) that has, at first sight, very little to do with the physical Coulomb repulsion. However, the model is often used to generate numerically (in exact-diagonali-sation calculations) the Laughlin state, which may then be compared to the Coulomb potential decomposed in Haldane's pseudopotentials. This procedure has shown that the aughlin state generated in this manner has an overlap of more than 99% with the state obtained from the Coulomb potential [63, 64], which is amazingly high for a wave function obtained from a well-educated guess. This high accuracy of Laughlin's wave function may be understood in the following manner: when one decomposes the Coulomb interaction potential in Haldane's pseudopotentials, one obtains a monotonically decreasing function when plotted as a function of m (see Fig. 4.2). Furthermore, the component  $v_1$  is much larger than  $v_3$  and all other pseudopotentials  $v_m$ with higher values of m.<sup>10</sup> These higher terms may be treated in a perturbative manner and do not change the ground state which is protected by the abovementioned gap on the order of  $v_1 > v_m$ , with m > 1.

Furthermore, we mention that, apart from its successful verification by exactdiagonalisation calculations [63, 64], Laughlin, in his original paper [14], showed within a variational calculation that the quantum liquid described by his wave

<span id="page-72-1"></span><sup>&</sup>lt;sup>10</sup>One has  $v_1/v_3 \simeq 1.6$  in the LLL. Notice that pseudopotentials with even angular momentum quantum number m do not play any physical role because of the fermionic nature of the electrons.

function \(4.3\) has indeed a lower energy than the previously proposed WC. Again the reason for this unexpected feature is the capacity of Laughlin's wave function, which varies as r <sup>2</sup><sup>m</sup> when two particles i and j approach each other with r = |z<sup>i</sup> − zj|, to screen the short-range components of the interaction potential. Notice that for a WC of fermions, the corresponding N-particle wave function decreases as r 2 , as dictated by the Pauli principle.

#### <span id="page-73-0"></span>4.2.3 Quasi-particles and quasi-holes with fractional charge

Until now, we have discussed some ground-state properties of Laughlin's wave function. We have seen that the Laughlin state at ν = 1/m is insensitive to the short-range components of the interaction potential described by Haldane's pseudopotentials vm′ with m′ < m, whereas excited states must be separated from the ground state by a gap characterised by these short-range pseudopotentials. However, we have not characterised so far the nature of the excitations.

There are two different sorts of excitations: (i) elementary excitations (quasiparticles or quasi-holes) that one obtains by adding or removing charge from the system, and (ii) collective excitations at fixed charge. The latter are simply a charge-density-wave excitation which consist of a superposition of particle-hole excitations at a fixed wave vector q (the momentum of the pair) and which may be shown to be gapped at all values of q. Its dispersion reveals a minimum (called magneto-roton minimum) at a non-zero value of the wave vector that indicates a certain tendency to form a ground state with modulated charge density, such as a WC. The characteristic dispersion relation of these collective excitations is shown in Fig. 4.3\(a). However, we do not discuss collective excitations here and refer the interested reader to the literature for a more detailed discussion \[65, 1, [4\]](#page-114-3), and concentrate here on a presentation of the elementary excitations.

#### Quasi-holes

Elementary excitations are obtained when sweeping the filling factor slightly away from ν = 1/m. Remember that there are two possibilities for varying the filling factor: adding charge to the system by changing the electronic density or adding (or removing) flux by varying the magnetic field. Remember further see Eq. [\(4.4\)] that the number of flux is intimitely related to the number of zeros in Laughlin's wave function. We therefore consider the ansatz

<span id="page-73-1"></span>
$$\psi_{qh}\left(z_{0},\left\{z_{j},z_{j}^{*}\right\}\right) = \prod_{j=1}^{N} (z_{j}-z_{0}) \psi_{m}^{L}\left(\left\{z_{j},z_{j}^{*}\right\}\right)$$
(4.12)

for an excited state. Each electron at the positions z<sup>j</sup> thus "sees" an additional zero at z0. In order to verify that this wave function adds indeed another flux quantum to the system, we may expand Laughlin's wave function \(4.3\) formally

![](images/_page_74_Figure_2.jpeg)

![](images/_page_74_Figure_3.jpeg)

<span id="page-74-0"></span>Figure 4.3: (a) Dispersion relation for collective charge-density-wave excitations (Girvin, MacDonald and (Platzman, 1986; Girvin, 1999). The continuous lines have been obtained in the so-called single-mode approximation (Girvin, MacDonald and (Platzman, 1986) for the Laughlin states at  $\nu=1/3$ , 1/5 and 1/7, whereas the points are exact-diagonalisation results (Haldane and Rezayi, 1985; Fano, (Ortolani and Colombo, 1986). The arrows indicated the characteristic wave vector of the WC state at the corresponding densities. (b) Quasi-hole excitation. Each electron jumps from the state m to the next-higher angular momentum state m+1.

in a polynomial,

$$\psi_m^L(\{z_j,z_j^*\}) = \sum_{\{m_i\}} \alpha_{m_1,...,m_N} z_1^{m_1} ... z_N^{m_N} e^{-\sum_j |z_j|^2/4},$$

where the  $\alpha_{m_1,...,m_N}$  describe the expansion coefficients. We now choose the position  $z_0$  at the centre of the disc, in which case the wave function of the excited state (4.12) simply reads

$$\psi_{qh}(\{z_j, z_j^*\}) = \sum_{\{m_i\}} \alpha_{m_1, \dots, m_N} z_1^{m_1 + 1} \dots z_N^{m_N + 1} e^{-\sum_j |z_j|^2 / 4},$$

i.e. each exponent is increased by one,  $m_i \to m_i + 1$ . This may be illustrated in the following manner: each electronjumps from the angular momentum state m to a state in which the angular momentum is increased by one (see Fig. 4.3), leaving behind an empty state at m = 0. The excitation is therefore called a quasi-hole as we have already suggested by the subscript in Eq. (4.12). This also affects the quantum state with highest angular momentum M, i.e. we have increased the sample size by the surface occupied by one flux quantum, while keeping the number of electrons fixed.<sup>11</sup> Furthermore, this quasi-hole is

<span id="page-74-1"></span> $<sup>\</sup>overline{\ }^{11}$ Naturally, the total surface of the quantum Hall system remains constant, but physically we have slightly increased the B-field. Each quantum state occupies then an infinitesimally

![](images/_page_75_Picture_0.jpeg)

 $\Delta N$  is simply given by

Quasi-particles

LLL,

 $M = N_B \to N_B + 1.$ 

i.e. the quasi-hole carries fractional charge.

that the relation between the extra flux  $\Delta N_B$  and the compensating extra charge

<span id="page-75-1"></span> $m\Delta N = \Delta N_B \qquad \Leftrightarrow \qquad \Delta N = \frac{\Delta N_B}{m} \,.$ 

This very important result is somewhat unexpected: in order to compensate one additional flux quantum ( $\Delta N_B = 1$ ), one would need to add the m-th fraction of an electron. The charge deficit caused by the quasi-hole excitation is therefore  $e^* = \frac{e}{m}$ ,

In the preceding paragraph, we have considered a quasi-hole excitation that is obtained by introducing an additional flux quantum in the system [or, mathematically, an additional zero in the Laughlin wave function, see Eq. (4.12)]. Naturally, one may also *lower* the number of flux quanta by one in which case one obtains a quasi-particle excitation with opposite vorticity as compared to that of the quasi-hole excitation. This opposite vorticity suggests that we use a prefactor  $\prod_{j=1}^{N} (z_j^* - z_0^*)$ , instead of  $\prod_{j=1}^{N-1} (z_j - z_0)$  as in the expression (4.12), in order to create a quasi-particle excitation at the position  $z_0$ . Remember, however, that the resulting wave function would have unwanted components in higher LLs because the analyticity condition of the LLL is no longer satisfied. In order to heal the quasi-particle expression, one formally projects it into the

<span id="page-75-0"></span> $\psi_{qp}\left(z_{0},\left\{z_{j},z_{j}^{*}\right\}\right) = \mathcal{P}_{LLL}\prod_{i=1}^{N}(z_{j}^{*}-z_{0}^{*})\,\psi_{m}^{L}\left(\left\{z_{j},z_{j}^{*}\right\}\right).$ 

smaller surface  $2\pi l_B^2$ , such that the system may accommodate for one more quantum state,

(4.13)

(4.14)

(4.15)

![](images/_page_76_Picture_0.jpeg)

<span id="page-76-2"></span>(black arrows). (b) Strong-backscattering limit. If one increases the side-gate voltage  $V_{sg}$ , the incompressible  $\nu = 1/3$  liquid is eventually cut into two parts separated by a fully depleted region ( $\nu = 0$ ). In this case, backscattering is the majority process (black arrow), and a tunneling may occur over the depleted region such that a particle injected at the left contact may still reach the right

There are several manners of taking into account this projection  $\mathcal{P}_{LLL}$ . A common one consists of replacing each occurence of the non-analytic variables  $z_j^*$  (and powers of them) in the polynomial part of the wave function by a derivative with respect to  $z_j$  in the same polynomial [67]. By partial integration, this amount to deriving the Gaussian factor by  $(\partial_{z_j})^m$  which, up to a numerical prefactor, yields exactly the non-analytic polynomial factor  $z_j^{*m}$ . We will encounter this projection scheme again in the discussion of the CF generalisation

That the fractional charge of Laughlin quasi-particles<sup>12</sup> is not only a mathematical concept but a physical reality has been proven in a spectacular manner

12 From now on, we use the term "(Laughlin) quasi-particles" generically in order to denote

Experimental observation of fractionally charged quasi-

one (grey arrows).

<span id="page-76-0"></span>4.2.4

of Laughlin's wave function (Sec. 4.4.1).

particles

<span id="page-76-1"></span>quasi-particles and quasi-holes.

![](images/_page_77_Picture_0.jpeg)

<span id="page-77-0"></span>A compelling physical picture of Laughlin's wave function (4.3) and the properties of its elementary excitations (4.12) and (4.15) with fractional charge has been provided by Laughlin himself [14], in terms of an analogy with a *classical 2D one-component plasma*. In the present subsection, we present the basic ideas and results of this plasma analogy, for completeness and pedagogical reasons. However, no new results will come out of this analogy here, as compared to

Remember from basic quantum mechanics that the modulus square of a quantum-mechanical wave function may be interpreted as a statistical probability distribution. For Laughlin's wave function (4.3), one obtains the probability

 $\left|\psi_{m}^{L}\left(\{z_{j}\}\right)\right|^{2} = \prod_{i < j} \left|z_{i} - z_{j}\right|^{2m} e^{-\sum_{j} |z_{j}|^{2}/2}.$ 

Now, remember from classical statistical mechanics that a probability distribution in the canonical ensemble is the Boltzmann weight,  $\exp(-\beta \mathcal{H})$ , of some Hamiltonian  $\mathcal{H}$  and that the classical partition function, which encodes all relevant statistical information, is obtained from a sum over the Boltzmann weights of all possible configurations  $\mathcal{C}$ ,  $\mathcal{Z} = \sum_{\mathcal{C}} \exp[-\beta \mathcal{H}(\mathcal{C})]$ . Laughlin's plasma analogy consists precisely of the identification of the modulus square of his wave

<span id="page-77-1"></span><sup>13</sup>Later this kind of experiment has been repeated for other FQHE states.

those derived above.

distribution

function with the Boltzmann weight of some mock Hamiltonian  $U_{cl}$ .<sup>14</sup> The mock Hamiltonian may be obtained exactly from this identification,

<span id="page-78-4"></span>
$$-\beta U_{cl} = \ln |\psi_m^L(\{z_j\})|^2,$$
 (4.16)

and one obtains, by choosing somewhat artificially  $\beta = 2/q$ , 15

<span id="page-78-2"></span>
$$U_{cl} = -q^2 \sum_{i \le j} \ln|z_i - z_j| + q \sum_j \frac{|z_j|^2}{4}.$$
 (4.17)

This is nothing other than the classical Hamiltonian of a 2D one-component plasma, in terms of the charge

<span id="page-78-3"></span>
$$q = m = 2s + 1 (4.18)$$

of the plasma particles. The first term of Eq. (4.17) reflects the interactions between the charged plasma particles, whereas the second term describes their interaction with a neutralising background of positive charge, as in the case of the jellium model of the Coulomb gas [52, 53]. This may be seen best with the help of Poisson's equation,  $-\Delta\phi = 2\pi q n_q(\mathbf{r})$ , for an electrostatic 2D potential due to the charge density  $qn_q$ . The first term describes then indeed particles with charge q interacting via the 2D Coulomb interaction potential  $\phi(\mathbf{r}) = -\ln(|\mathbf{r}|/l_B)$ , and the second term is the interactions with the neutralising background because  $\Delta|\mathbf{r}|^2/4l_B^2 = 1/l_B^2 = 2\pi n_B$ , where the flux density  $n_B$  may thus be viewed as the charge density of the positively charged background.

In order to minimise the energy of the mock Hamiltonian  $U_{cl}$ , which corresponds to a distribution of highest weight, the 2D plasma thus needs to be charge-neutral, i.e. the charge density of the plasma particles  $qn_{el}$  must be compensated by that of the background  $n_B$ ,

$$n_B - q n_{el} = 0, (4.19)$$

which, together with Eq. (4.18), yields nothing other than the relation between the filling factor  $\nu$  and the exponent in Laughlin's wave function (4.5),  $\nu = n_{el}/n_B = 1/m$ .

The plasma analogy does not only apply to the ground-state wave function (4.3) but also to the quasi-hole excitation (4.12). The additional factor  $\prod_{j=1}^{N} (z_j - z_0)$  in the quasi-hole wave function (4.12) yields, within the plasma analogy (4.16), an additional term

$$V = -q \sum_{j=1}^{N} \ln|z_j - z_0| \tag{4.20}$$

to the mock Hamiltonian (4.17),  $U_{cl} \rightarrow U_{cl} + V$ . This additional term may be interpreted as the interaction of the plasma particles with an "impurity"

<span id="page-78-0"></span><sup>&</sup>lt;sup>14</sup>mock: singlish for fake; mainly used the description of Singaporean catering food.

<span id="page-78-1"></span> $<sup>^{15}\</sup>mathrm{Notice}$  that Laughlin's wave function describes a system at T=0, such that temperature does not intervene in the expressions. The choice is purely formal.

![](images/_page_79_Picture_2.jpeg)

Figure 4.5: (a) Process in which a particle A moves on a path  $\mathcal{C}$  around another particle B. In three space dimensions, one may profit from the third direction (z-direction) to lift the path over particle B and thus to shrink the path into a single point. (b) Process equivalent to moving A on a closed path around B which consists, apart from a topologically irrelevant translation, of two successive exchanges of A and B.

<span id="page-79-2"></span>of unit charge at the position  $z_0$ . In order to maintain charge neutrality, the impurity needs to be screened by the plasma particles. Since the charge of each plasma particle is q=m=2s+1 and thus greater than unity, one needs 1/q plasma particles to screen the impurity of charge one. Remember that each plasma particle represents one electron of unit charge in the original Laughlin liquid. One therefore obtains the same charge fractionalisation of the Laughlin quasi-particle (4.14),  $e^*=e/m$ , as in the original quantum model.

#### <span id="page-79-1"></span><span id="page-79-0"></span>4.3 Fractional Statistics

#### 4.3.1 Bosons, fermions and anyons – an introduction

One of the most exotic consequences of charge fractionalisation in 2D quantum mechanics, exemplified by Laughlin quasi-particles, is fractional statistics. Remember that, in three space dimensions, the quantum-mechanical treatment of two and more particles yields a superselection rule according to which quantum particles are, from a statistical point of view, either bosons or fermions. This superselection rule is no longer valid in 2D (two space dimensions), and one may find intermediate statistics between bosons and fermions. The corresponding particles are called anyons, because the statistics may be any. The present section is meant to illustrate these amazing aspects of 2D quantum mechanics, and we try to avoid a too formal or mathematical treatment. We refer, again, the interested reader to the more detailed literature [70].

In order to illustrate the different statistical (i.e. exchange) properties of two quantum particles in three and two space dimensions, consider a particle A that moves adiabatically on a closed path  $\mathcal{C}$  in the xy-plane around another one B of the same species (see Fig. 4.5). We choose the path to be sufficiently far away from particle B and the two particles to be sufficiently localised such that we can neglect corrections due to the overlap between the two corresponding wave functions. Notice first that such a process  $\mathcal{T}$  is equivalent, apart from a topologically unimportant translation, to two successive exchange processes  $\mathcal{E}$ , in which one exchanges the positions of A and B. Algebraically, this may be

Fractional Statistics 81

expressed in terms of the corresponding operators as

<span id="page-80-0"></span>
$$\mathcal{E}^2 = \mathcal{T}$$
 or  $\mathcal{E} = \pm \sqrt{\mathcal{T}},$  (4.21)

modulo a translation.

Let us discuss first the three-dimensional case. Because of the presence of the third direction (z-direction), one may elevate the closed path in this direction while keeping the position of particle A fixed in the xy plane. We call the elevated path  $\mathcal{C}'$ . Furthermore, one may now shrink the closed loop  $\mathcal{C}'$  into a single point at the position A without passing by the position of particle B which remains in the xy-plane. This final (point-like) path is called  $\mathcal{C}''$ . Although this procedure may seem somewhat formal, a quantum-mechanical exchange process does principally not specify the exchange path in order to define whether a particle is a boson or a fermion, but only its topological properties. From a topological point of view, all paths that may be continuously deformed into each other define a homotopy class [71]. Equation (4.21) must therefore be viewed as an equation for homotopy classes in which a simple translation and an allowed deformation are irrelayant. As a consequence of these considerations, the simple point-like path  $\mathcal{C}''$  at the position of particle A, which may be formally described by C'' = 1, is in the same homotopy class as the original path C. Therefore, the associated processes are the same, and one has

$$\mathcal{T} = \mathcal{T}(\mathcal{C}) = \mathcal{T}(\mathcal{C}'') = \mathbb{1}$$
 and thus  $\mathcal{E} = \sqrt{\mathbb{1}}$ , (4.22)

where the last equation is symbolic in terms of the one operator. It indicates that the quantum-mechanical operator  $\mathcal{E}$ , corresponding to particle exchange, has two eigenvalues that are the two square roots of unity,  $e_B = \exp(2i\pi) = 1$  and  $e_F = \exp(i\pi) = -1$ . This is precisely the above-mentioned superselection rule, according to which all quantum particles in three space dimensions are either bosons  $(e_B = 1)$  or fermions  $(e_F = -1)$ .

In two space dimensions, this topological argument yields a completely different result. It is not possible to shrink a path  $\mathcal C$  enclosing the second particle B into a single point at the position of A, without passing by B itself. This means that the position of B must be an element of the path at a certain moment of the shrinking process, which cannot profit from a third dimension in order to elevate the loop on which it moves above the xy-plane. The single point still represents a homotopy class of paths, but these paths do not enclose another particle, and  $\mathcal C$  is therefore an element of another homotopy class, i.e. the one of all paths starting from A and enclosing only the particle B. If there are more than two particles present, the homotopy classes are described by the integer number of particles enclosed by the paths in this class. From an algebraic point of view, the exchange processes are no longer described by the two roots of unity, 1 and -1, but by the so-called braiding group, and the classification in bosons and fermions is no longer valid. In the simplest case of Abelian statistics,  $^{16}$  one

<span id="page-80-1"></span><sup>&</sup>lt;sup>16</sup>There are more complicated cases of non-Abelian statistics, in which the exchange processes of more than two different particles no longer commute, but we do not discuss this case here and refer the reader to the review by Nayak *et al.* [70].

needs to generalise the commutation relation

<span id="page-81-1"></span>
$$\psi(\mathbf{r}_1)\psi(\mathbf{r}_2) = \pm \psi(\mathbf{r}_2)\psi(\mathbf{r}_1),\tag{4.23}$$

for bosons and fermions, respectively, to

<span id="page-81-2"></span>
$$\psi(\mathbf{r}_1)\psi(\mathbf{r}_2) = e^{i\alpha\pi}\psi(\mathbf{r}_2)\psi(\mathbf{r}_1), \tag{4.24}$$

where  $\alpha$  is also called the *statistical angle*. One has  $\alpha=0$  for bosons and  $\alpha=1$  for fermions, and all other values of  $\alpha$  in the interval between 0 and 2 for anyons. Sometimes anyonic statistics is also called *fractional statistics* – indeed all physical quasi-particles, such as those relevant for the FQHE, have an angle that is a fractional (or rational) number, but there is no fundamental objection that irrational values of the statistical angle should be excluded.

Before discussing the anyonic nature of Laughlin quasi-particles, we need to mention an important issue in these statistical considerations. We know that fermions are forced to satisfy Pauli's principle which excludes double occupancy of a single quantum state, whereas the number of bosons per quantum state is unrestricted. What about anyons then? In the context of quantum fields the Pauli principle yields, via Eq. (4.23) for  $\mathbf{r} = \mathbf{r}_1 = \mathbf{r}_2$ ,

$$\psi(\mathbf{r})\psi(\mathbf{r}) = 0.$$

For an arbitrary statistical angle, one obtains in the same manner, from Eq. (4.24),

<span id="page-81-3"></span>
$$(1 - e^{i\alpha\pi}) \psi(\mathbf{r})\psi(\mathbf{r}) = 0, \tag{4.25}$$

which may be viewed as a generalised Pauli principle for 2D anyons [72]. Only if  $\alpha = 0$  modulo 2, we may have  $\psi(\mathbf{r})\psi(\mathbf{r}) \neq 0$  in order to satisfy Eq. (4.25). Otherwise, when  $\alpha \neq 0$  modulo 2, we necessarily have  $\psi(\mathbf{r})\psi(\mathbf{r}) = 0$ . Anyons are, thus, from an exclusion-principle point of view more similar to fermions than to bosons.

#### <span id="page-81-0"></span>4.3.2 Statistical properties of Laughlin quasi-particles

We may now apply the above general statistical considerations to the case of Laughlin quasi-particles. The basic idea is to describe the statistical angle as an Aharonov-Bohm phase due to some gauge field that is generated by the flux bound to the charges included in a closed loop  $\partial \Sigma$ . This closed loop, around which a quasi-particle moves adiabatically, encloses a surface  $\Sigma$ . The gauge field is not to be confunded with the one which generates the true magnetic field B – it is rather a mock (or fake) field  $\mathbf{A}_M$  (with  $\mathbf{B}_M = \nabla \times \mathbf{A}_M$ ) that generates the flux bound, e.g., by the electrons in the Laughlin liquid via the relation (4.4). We consider the case where the area  $\Sigma$  is filled with  $N_{el}(\Sigma)$  electrons condensed in an incompressible quantum liquid described by Laughlin's wave function (4.3) and  $N_{qh}(\Sigma)$  quasi-hole excitations (4.12), such that there are two contributions to  $B_M = |\mathbf{B}_M|$ ,

<span id="page-81-4"></span>
$$B_M \Sigma = N_{\text{flux}} \frac{h}{e} = \left[ m N_{el}(\Sigma) + N_{qh}(\Sigma) \right] \frac{h}{e} . \tag{4.26}$$

![](images/_page_82_Picture_0.jpeg)

enclosing condensed electrons. However, had we chosen an electron rather than

e e

would give rise to a statistical angle α = mNel(Σ).17 If we have only one electron enclosed by the path, Nel(Σ) = 1, the statistical angle is simply the odd integer

A more interesting situation arises when the path encloses Laughlin quasi-

Nqh = 2π

Consider a single quasi-hole in the area Σ, Nqh = 1: one encounters the rather unusual situation in which the Aharonov-Bohm phase is a fraction of 2π, and the associated statistical angle is α = 1/m. This illustrates that Laughlin quasiholes are indeed anyons with fractional statistics, as we have argued above.

<span id="page-82-0"></span>4.4 Generalisations of Laughlin's Wave Function

<span id="page-82-1"></span>Although Laughlin's wave function \(4.3\) has been extremely successful in the description of the FQHE at ν = 1/3 and 1/5, it is not capable of describing all observed FQHE states. Indeed, there are e.g. FQHE states at ν = 2/5, 3/7, 4/9, ... corresponding to the series p/(2p + 1), or more generally to p/(2sp + 1), in <sup>17</sup>Remember that the statistical angle is defined with respect to an exchange process E which is the square root of the process T considered here Eq. [\(4.21\)]. The relation between the statistical angle and the Aharononv-Bohm phase is therefore Γ = 2πα and not πα.

Nqh m

. (4.28)

mNel(Σ),

a quasi-hole to move along the path ∂Σ, the Aharonov-Bohm phase,

Γel−el = 2π

m, which is equal to 1 (modulo 2), as it should be for fermions.

Γel = 2π

e ∗ e

holes, in which case the Aharonov-Bohm phase reads

![](images/_page_83_Picture_0.jpeg)

<span id="page-83-1"></span>fermion (CF) theory, which we present below. Furthermore, even-denominator FQHE states have been observed at ν = 5/2 and 7/2 [\[17\]](#page-115-3), in the first excited LL (n = 1), and, in wide quantum wells or bilayer quantum Hall systems, at ν = 1/2 and ν = 1/4 \[73, [74\]](#page-117-20). Whereas the latter may be understood within a multi-component picture, which we will briefly introduce in Chap. 5, the states at ν = 5/2 and 7/2 may find their explanation in terms of a so-called Pfaffian wave function. Both the CF and the Pfaffian wave functions are sophisticated

Soon after the discovery of the most prominent FQHE state at ν = 1/3, a lot of other states have been observed at the filling factors ν = p/(2sp + 1). In a first theoretical approach, these states were interpreted in the framework of a hierarchy scheme \[62, [75\]](#page-118-0) according to which the quasi-particles of the Laughlin (parent) state, such as ν = 1/3, condense themselves into a Laughlintype (daughter) state, due to their residual Coulomb repulsion – remember that

the 2/5 state would be the daughter state formed of Laughlin quasi-particle

An alternative picture, though related to the above-mentioned hierarchy scheme, was proposed by Jain in 1989 \[15, [16\]](#page-115-2). The basic idea consists of a reinterpretation of Laughlin's wave function \(4.3\): consider only the polynomial

<sup>∗</sup> = e/m. In this picture,

<sup>2</sup>/4) being an ubiquitous factor which finally

generalisations of Laughlin's original idea.

the Laughlin quasi-particles are charged with charge e

P<sup>N</sup> j |z<sup>j</sup> |

<span id="page-83-0"></span>4.4.1 Composite Fermions

excitations of the 1/3 state.

part, the Gaussian exp(−

<span id="page-84-0"></span>![](images/_page_84_Picture_0.jpeg)

In the case of the above decomposition (4.29) of Laughlin's wave function, the vortex part attaches s pairs of flux quanta to each particle position and therefore does not affect the statistical properties of the wave function. The

 $\chi_{\nu^*=1}(\{z_j\}) = \prod_{k < l} (z_k - z_l)$ 

is indeed fermionic and corresponds, as we have mentioned in Sec. 4.2.1, to a completely filled LL at a virtual (CF) filling factor of  $\nu^* = 1$ , the true filling factor being still  $\nu = 1/(2s+1)$ . This is schematically represented in Fig. 4.6. Jain's generalisation consists of replacing the term  $\prod_{k< l} (z_k - z_l)$  by any other Slater determinant  $\chi_{\nu^* = p}(\{z_j, z_j^*\})$  of p completely filled LLs, with a CF

<span id="page-84-1"></span> $\psi^{J}(\{z_{j}, z_{j}^{*}\}) = \mathcal{P}_{LLL} \prod_{k < l} (z_{k} - z_{l})^{2s} \chi_{\nu^{*} = p}(\{z_{j}, z_{j}^{*}\}),$ 

where we need to take into account the same projection  $\mathcal{P}_{LLL}$  to the LLL as in the case of quasi-particle excitations (4.15) because, contrary to the  $\nu^* = 1$  case, the wave function  $\chi_{\nu^*=p}(\{z_j, z_i^*\})$  has by construction non-analytic components,

Jain's wave function (4.30) may be illustrated in the following manner. Via the first factor  $\prod_{k < l} (z_k - z_l)^{2s}$ , we have effectively bound 2s flux quanta to

(4.30)

second factor

filling factor  $\nu^* = p$ ,

i.e. components in higher (CF) LLs.

each of the electrons, as we have already mentioned above. This novel type of particle is what we call the composite fermion (CF). The residual (free) flux quanta effectively determine the effective number of states per (CF) LL,

$$N_B \to N_B^* = N_B - 2sN_{el},$$

which correspond to a renormalised magnetic field

<span id="page-85-2"></span>
$$B \to B^* = B - 2s \left(\frac{h}{e}\right) n_{el}. \tag{4.31}$$

Similarly the CF filling factor is defined with respect to the renormalised number of flux quanta,

$$\nu^* = \frac{N_{el}}{N_B^*} \qquad \Rightarrow \qquad \nu^{*-1} = \nu^{-1} - 2s,$$
 (4.32)

which leads to the relation

$$\nu = \frac{\nu^*}{2s\nu^* + 1} \tag{4.33}$$

between the CF filling factor and the usual one ν Eq. [\(2.44\)]. For completely filled LLs, ν <sup>∗</sup> = p, this yields the above-mentioned series

<span id="page-85-1"></span>
$$\nu = \frac{p}{2sp+1} \tag{4.34}$$

for the FQHE states which may thus be interpreted as IQHE states of CFs. To be explicit, the physical picture of CF theory is the following: the ground state is described by the wave function \(4.30\), which describes an incompressible quantum liquid in the same manner as Laughlin's wave function does. The elementary excitation in the CF theory consists of a CF promoted to the next higher CF LL, which is separated from the ground state by an energy gap, in analogy with the electron as compared to n completely filled (electronic) LLs in the IQHE.18 Again, these elementary CF excitations become localised by the sample impurities, and one therefore obtains a plateau in the Hall resistance which is thus quantised.

Numerically, Jain's CF wave function \(4.30\) has been successful in the description of the series \(4.34\) of FQHE states: even if the overlap with the exact ground states decreases when the quantum number p, which describes the number of completely filled CF LLs, increases, the overlap is still reasonably high (above 95%) for the number of particles accessible in state-of-the-art exact diagonalisation calculations. Notice, however, that the physical interpretation is more involved as compared to Laughlin's wave function, because of the LLL projection PLLL, which is rather complicated to implement in analytical as well as numerical calculations. For a further review of CF theory, we refer the interested reader to the literature. The above-mentioned wave-function approaches are thoroughly reviewed in Jain's recent book [\[76\]](#page-118-1). Furthermore, there have

<span id="page-85-0"></span><sup>18</sup>Remember, however, that the energy scale of this gap is not given in terms of a kinetic energy ¯heB/m, but in terms of the Coulomb interaction e <sup>2</sup>/ǫlB.

been field-theoretical approaches beyond the numerical wave-function description presented above, such as in terms of Chern-Simons theories [77, 78] or in terms of a Hamiltonian theory [5]. For a review of these complementary theories we refer the reader to the book edited by Heinonen [79] or the excellent pedagogical review by Murthy and Shankar [5].

#### <span id="page-86-0"></span>4.4.2 Half-filled LLs and Pfaffian states

Within the CF picture, we have seen that the effective magnetic field becomes renormalised due to flux attachment [Eq. (4.31)]. An interesting situation arises when the filling factor is  $\nu=1/2$ , which corresponds to the limit  $p\to\infty$  in Eq. (4.34). In this limit the effective magnetic field (4.31) vanishes,  $B^*=0$ , and one may then expect the corresponding phase to be described in terms of a metallic state, such as a Fermi liquid that one would obtain for electrons when the magnetic field vanishes. A natural ansatz for the N-particle wave function of such a Fermi-liquid state is given by the Slater determinant

$$\psi_{FL} = \det\left(e^{i\mathbf{k}_i \cdot \mathbf{r}_j}\right),\,$$

where the N electrons occupy the states described by the wave vectors  $\mathbf{k}$ , i=1,...,N, the modulus of which is delimited by the Fermi wave vector  $|\mathbf{k}_i| \leq k_F$ , and  $\mathbf{r}_j$  is the position of the j-th particle. Notice that this state is nevertheless unappropriate in the description of a state in the LLL. Indeed, if the scalar product in the exponent is rewritten in terms of complex variables,  $\mathbf{k}_i \cdot \mathbf{r}_j = (k_i z_j^* + k_i^* z_j)/2$ , one realises that the Fermi-liquid state violates the LLL condition of analyticity. Formally, one may again avoid this problem by projecting the Fermi-liquid state into the LLL, and one obtains indeed a state,

<span id="page-86-1"></span>
$$\psi_{FL}^{\nu=1/2} = \mathcal{P}_{LLL} \prod_{k < l} (z_k - z_l)^2 \det \left( e^{i\mathbf{k}_i \cdot \mathbf{r}_j} \right), \tag{4.35}$$

that was proposed by Rezayi and Read for the description of a compressible metallic state at  $\nu=1/2$  [80]. The first term is the same factor as in CF theory, which attaches 2 flux quanta to each particle and which cancels thus the external magnetic field,  $B^*=B-2(h/e)n_{el}=0$ .

Because the wave function (4.35) describes a compressible state, one should not observe a quantised Hall resistance, in agreement with most experimental data. A FQHE at  $\nu=1/2$  (and 1/4) has only been observed in very wide quantum wells [73, 74], which are likely to be described by two-component wave functions [81] that we will briefly introduce in Chap. 5.

In contrast to the LLL, the half-filled LL n=1 reveals, in both spin branches, a FQHE (5/2 and 7/2 states). The difference between the half-filled LL n=0 and n=1 is due to a different effective interaction potential that takes into account the wave function overlap between two (interacting) particles, which we do not discuss in detail here. Indeed, the Fermi-liquid-like state (4.35) turns out to be quite unstable with respect to particle pairing. This is reminiscent of the BCS (Bardeen-Cooper-Schrieffer) instability of a conventional Fermi liquid

that gives rise to superconductivity [52, 66], although the glue between the particles is no longer a phonon-mediated attractive interaction, but only the repulsive Coulomb interaction in a strong magnetic field. As we have already mentioned in Sec. 4.2.2, such an interaction may yield a discrete two-particle spectrum, in contrast to a repulsive interaction in the absence of a magnetic field. As a consequence, pairing may occur at certain relative angular momenta for particular pseudopotential sequences and for sufficiently high filling factors. <sup>19</sup> In the present case, one may exclude s-wave pairing, i.e. in the relative angular momentum state with m=0 due to the Pauli principle, and the most natural candidate would therefore be p-wave pairing in the relative angular momentum state m=1 [19].

A wave function that accounts for p-wave pairing was proposed by Moore and Read in 1991 [18],

$$\psi_{MR}(\{z_j\}) = \text{Pf}\left(\frac{1}{z_i - z_j}\right) \prod_{k < l} (z_k - z_l)^2,$$
 (4.36)

where we have again omitted the ubiquitous Gaussian factor. As for the CF wave functions (4.30) and the Rezayi-Read wave function (4.35), the factor  $\prod_{k < l} (z_k - z_l)^2$  attaches two flux quanta to each electron and therefore does not change the statistical properties of the wave function. If the wave function consisted only of this factor (times the Gaussian), one would have a bosonic Laughlin wave function that describes an incompressible quantum liquid at the desired filling factor  $\nu = 1/2$ . However, it does not have the correct statistical properties. This problem is healed by the first factor  $Pf[1/(z_i - z_j)]$  which represents the Pfaffian of the  $N \times N$  matrix  $\mathcal{M}_{ij} = 1/(z_i - z_j)$ . The Pfaffian may be viewed as the square root of the more familiar determinant,  $Pf(\mathcal{M}) =$  $\sqrt{\det(\mathcal{M})}$ , and has the same anti-symmetric properties as the determinant in an exchange of two particles i and j, such that it generates a fermionic wave function. Notice, furthermore, that this Pfaffian seems, at first sight, to take away some of the zeros such that one could expect the filling factor to increase. However, the function  $\prod_{k < l} (z_k - z_l)^2$  is a product of  $N(N-1) \sim N^2$  terms, whereas the Pfaffian is a sum of products of  $N/2 \sim N$  terms. Therefore, the number of zeros, and thus the filling factor, is unchanged in the thermodynamic limit,  $N \to \infty$ .

A particularly interesting feature of the Pfaffian state are the quasi-particle excitations of charge e/4 which satisfy non-Abelian anyonic statistics [18], in contrast to the corresponding excitations of Laughlin's (4.3) or Jain's (4.30) wave functions. These non-Abelian quasi-particles are currently investigated in detail within the proposal of topologically-protected quantum computation [83]. A more detailed discussion of this issue is beyond the scope of these lecture notes, and we refer the reader to the review article by Nayak et al. [70].

<span id="page-87-0"></span><sup>&</sup>lt;sup>19</sup>There have been attempts in the literature to formalise this point [63, 82].

# <span id="page-88-0"></span>Chapter 5

# Brief Overview of Multicomponent Quantum-Hall Systems

## <span id="page-88-1"></span>5.1 The Different Multi-Component Systems

#### <span id="page-88-2"></span>5.1.1 The role of the electronic spin

In the preceding chapters, we have completely neglected the physical consequences of possible internal degrees of freedom, apart from an occasional degeneracy factor that has been smuggled in to account for experimental data. This choice has been made simply for pedagogical reasons, but it is clear that one prominent internal degree of freedom – the electronic spin – may not be put under the carpet so easily. Naively, one may expect that each LL is split into two distinct spin-branches separated by the energy gap ∆<sup>Z</sup> due to the Zeeman effect. If this gap is large, one may use the same one-particle arguments as in the case of the IQHE, but now for each spin branch separately: once the lowest spin branch of a paticular LL is completely filled, additional electrons must overcome an energy gap that is no longer given by the LL separation but by ∆Z. This would indeed not change the presented explanation of the IQHE – instead of a localised electron in the next higher LL, one simply needs to invoke localisation in the upper spin branch.

Also in the case of the FQHE, the explanation would need to be modified only in the fine structure if the Zeeman gap is sufficiently large. If the electrons fill partially the lower spin branch of the lowest (or any) LL, one may omit all transitions to the upper spin branch and argue that they constitute the highenergy degrees of freedom, in the same manner as inter-LL excitations in the case of the "spinless" fermions which we have discussed in Sec. 4.1.

However, the situation is not so easy as the above picture might suggest. Indeed, already in 1983 Halperin pointed out [\[84\]](#page-118-9) that the Zeeman gap in GaAs, with a g-factor of g=-0.4, is  $\Delta_Z=g\mu_BB=g(\hbar e/2m_0)B\simeq 0.33B[T]$  K and therefore much smaller than both the LL separation  $\hbar\omega_C=(\hbar e/m)B\simeq 24B[T]$  K, due to the rather small band mass  $(m=0.068m_0, \text{ in terms of the bare electron mass }m_0, \text{ in GaAs})$ , and the Coulomb energy scale  $V_C=e^2/\epsilon l_B\simeq 50\sqrt{B[T]}$  K with a dielectric constant of  $\epsilon\simeq 13$ . For a characteristic field of 6 T, for which one typically reaches the LLL condition  $\nu=1$ , one therefore has the energy scales

$$\Delta_Z \simeq 2 \,\mathrm{K} \ll \frac{e^2}{\epsilon l_B} \simeq 120 \,\mathrm{K} \lesssim \hbar \omega_C \simeq 140 \,\mathrm{K},$$
 (5.1)

in GaAs. The situation is qualitatively the same in graphene, where one finds for a field  $^1$  of 6  $\rm T$ 

$$\Delta_Z \simeq 7 \, \mathrm{K} \quad \ll \quad \frac{e^2}{\epsilon l_B} \simeq 620 \, \mathrm{K} \quad \lesssim \quad \sqrt{2} \frac{\hbar v}{l_B} \simeq 1000 \, \mathrm{K}, \tag{5.2}$$

for  $g\simeq 2$  and  $\epsilon\simeq 2.5,$  which are the appropriate values for graphene on a SiO<sub>2</sub> substrate.<sup>2</sup>

The inevitable consequence of these considerations is that, even if one may neglect the kinetic energy scale in a low-energy description of a partially filled LL, one cannot do so with the Zeeman energy scale. One must therefore take into account the electron spin within a two-component picture in which each quantum state  $|n, m\rangle$  is doubled,  $|n, m; \sigma\rangle$  with  $\sigma = \uparrow$  and  $\downarrow$ .

# <span id="page-89-0"></span>5.1.2 Graphene as a four-component quantum Hall system

Another multi-component system that we have already discussed is precisely graphene, not only because of the tiny Zeeman gap which requires to take into account the electronic spin, but also because of its double valley degeneracy due to the two inequivalent Dirac points situated at the corners K and K' in the first BZ. Each quantum state  $|n,m\rangle$  therefore occurs in four copies,  $|n,m;\sigma\rangle$  with  $\sigma=(K,\uparrow), (K,\downarrow), (K',\uparrow)$  and  $(K',\downarrow)$ . Formally this four-fold degeneracy may be described with the help of an SU(4) spin, whereas the two-fold spin degeneracy in GaAs, e.g., is represented by the usual SU(2) spin. Notice that it is very difficult in graphene to lift the valley degeneracy, and the associated energy scale is expected to be on the same order of magnitude as the Zeeman gap, i.e. it is tiny with respect to the one set by the Coulomb interactions.

#### <span id="page-89-1"></span>5.1.3 Bilayer quantum Hall systems

A third multi-component system that we would like to mention consists of a double quantum well [see Fig. 5.1(a)]. These bilayer systems, which are fabricated

<span id="page-89-2"></span><sup>&</sup>lt;sup>1</sup>Remember that this field is somewhat arbitrary because the situation  $\nu = 1$  may also be obtained easily for other fields by varying the gate voltage  $V_G$ .

<span id="page-89-3"></span> $<sup>^2</sup>$ Naturally, the dielectric constant depends on the dielectric environment around the graphene sheet and thus also on the substrate.

by molecular-beam epitaxy, consist of two quantum wells spatially separated by an insulating barrier that is on the same order of magnitude as the width of each of the wells. Formally, each of the wells (layers) may be described in terms of an SU(2) pseudo-spin,  $\sigma = \uparrow$  for an electron in the left well and  $\sigma = \downarrow$  for one in the right well. In contrast to the true electron spin, the Coulomb interaction does not respect this SU(2) symmetry – indeed, the repulsion is stronger between particles within the same layer (i.e. with the same pseudo-spin orientation) than between particles in different layers (with opposite pseudo-spin orientation) because, in the second case, electrons may not be brought together closer than the distance d between the layers. In order to minimise the interaction energy, it is therefore favourable to charge both layers equally. Alternatively, this may be viewed as some capacitive energy, if one interprets the two-layer system in terms of a capacitor, that favours an equal charge distribution between the two layers as compared to a charging of only one layer. Notice, furthermore, that tunneling, with the tunneling energy t, between the two quantum wells lifts the pseudo-spin degeneracy: whereas the symmetric superposition  $|+\rangle = (|\uparrow\rangle + |\downarrow\rangle)/\sqrt{2}$  of the layer pseudo-spin lowers the energy, the antisymmetric superposition  $|-\rangle = (|\uparrow\rangle - |\downarrow\rangle)/\sqrt{2}$  describes anti-binding. The energy separation between the associated subbands is given by  $\Delta_{SAS} = 2t$  [see Fig. 5.1(a)], but it may be strongly reduced experimentally with the help of a high potential barrier separating the two wells. The term  $\Delta_{SAS}$ , which plays the role of a Zeeman gap (though in the x-quantisation axis), may become the lowest energy scale in the system, such that the SU(2) pseudo-spin symmetry

<span id="page-90-0"></span>decreased as compared to a narrow quantum well.

<span id="page-91-0"></span>![](images/_page_91_Picture_0.jpeg)

In the remainder of this chapter, we discuss some aspects of correlated states that one encounters in multi-component quantum Hall systems in general, starting (Sec. 5.2) with the completely spin-polarised state at  $\nu=1$  (quantum Hall ferromagnet) and its various manifestations in the different quantum Hall systems described above. We will not discuss, for reasons of space limitation, the amazing physical properties of the elementary excitations of the quantum Hall ferromagnet, which is a topological spin-texture state (skyrmion), and refer the interested reader to the literature [86, 87, 4, 3]. In the line of the preceding chapter, we have chosen to discuss a generalisation of Laughlin's wave function, which we owe to Halperin [84], in order to account for the electronic spin (Sec. 5.3). These wave functions are further generalised to even more components than two, and we close this section with a discussion of their possible use in the

If one takes into account internal degrees of freedom, the state at  $\nu=1$  is no longer simply a Slater determinant of all occupied quantum states in the lowest LL, but one must take into account the macroscopic degeneracy due to the fact that each state  $|n,m\rangle$  may now be occupied by 0, 1 or 2 particles. In this sense the situation at  $\nu=1$  is much more similar to the FQHE in a partially filled LL than to the IQHE which one obtains for completely filled LL [86], and

description of multi-component FQHE states.

The State at  $\nu = 1$ 

<span id="page-91-1"></span>5.2

<span id="page-92-0"></span>![](images/_page_92_Picture_0.jpeg)

in the case of spinless fermions, it is simply the non-degenerate wave function described by a Slater determinant, whereas in the case of electrons with spin, the state is formed in order to minimise the mutual Coulomb repulsion.

<span id="page-92-2"></span> $\chi_{FM} = |\uparrow_1, \uparrow_2, ..., \uparrow_N\rangle,$ 

in order to form an overall wave function that is anti-symmetric. The subscript indicates the index of the particle that the spin is associated with. The global

 $\psi_{\nu=1,FM} = \prod_{k < l} (z_k - z_l) \otimes |\uparrow_1, \uparrow_2, ..., \uparrow_N \rangle.$ 

This is nothing other than a (spin) wave function of a quantum ferromagnet, similar to ferromagnetism in a usual Fermi liquid. Indeed, the spontaneous spin polarisation in a Fermi liquid is also due to a minimisation of the Coulomb  $\overline{\phantom{a}}^{3}$ This pseudopotential, as well as any other with an even value of m, does not play any physical role due to the Pauli principle if one considers only spinless electrons, as we have

(5.3)

(5.4)

freedom must be fully symmetric, e.g.

wave function, therefore, reads

<span id="page-92-1"></span>mentioned in Sec. 4.2.2.

Because the orbital wave function (4.7) for electrons with spin at  $\nu = 1$  is fully anti-symmetric, the spin wave function describing the internal degrees of

Brief Overview of Multicomponent Quantum-Hall Systems 94 repulsion by the formation of an anti-symmetric orbital wave function. Notice, however, that the spin polarisation in a Fermi liquid comes along with an energy cost as a consequence of the mismatch between the Fermi energies of spin-↑ and spin-\ electrons. The competition between the gain in interaction energy and the cost in kinetic energy determines the final polarisation of the system, which is never perfect. In the case of the quantum Hall ferromagnet, there is no cost in kinetic energy when the system is fully polarised because all quantum states have the same kinetic energy, and the system is therefore fully polarised. Collective excitations Because the spontaneous spin polarisation in the quantum Hall ferromagnet chooses, in the absence of a Zeeman effect, an arbitrary direction in the threedimensional spin space, one is confronted with a spontaneous SU(2) symmetry breaking. As a consequence of this broken continuous symmetry, there exists a gapless collective excitation (Goldstone mode) the energy of which tends to zero in the long wave-length limit. Indeed, even if we have chosen the ferromagnet in Eq. (5.3) to be oriented in the z-direction, any other orientation, such as the one described by the wave function

 $|\downarrow_1,\downarrow_2,...,\downarrow_N\rangle$  or  $\bigotimes_{j=1}^N|+_j\rangle=|+_1,+_2,...,+_N\rangle,$ where the  $+_j$  sign indicates the symmetric superposition  $|+_j\rangle = (|\uparrow_j\rangle + |\downarrow_j$  $\rangle)/\sqrt{2}$  of both spin orientations of the j-th electron, would also describe a ground

state. The Goldstone mode in the large wave-length limit may then be viewed as a global rotation of all spins into another ground-state configuration, which naturally does not imply an energy cost. In the case of a ferromagnet, the Goldstone mode is nothing other than the spin-density wave<sup>4</sup> that disperses as  $\omega \propto q^2$  in the small wave vector limit,  $ql_B \ll 1$ . At first sight, this mode seems in contradiction with the observation of a quantum Hall effect at  $\nu = 1$ , even in the absence of a Zeeman effect, which requires a gap as we have seen above. Notice, however, that this gap needs to be a transport gap in which a quasi-particle moves independently from a quasihole in order to transport a current. This is not the case in a spin wave with  $ql_B \ll 1$ , but one obtains freely moving quasi-particles and quasi-holes in the

is given by the exchange energy between particles of different spin orientation and that is proportional to the interaction energy scale  $e^2/\epsilon l_B$ , as in the case of the FQHE [87]. There are more exotic spin-texture excitations (skyrmions), which are described by a topological quantum number associated with the winding of the spin-texture. These are gapped excitation which carry an electric charge related <sup>4</sup>Remember that for a crystaline ground state (WC), the Goldstone mode is the acoustic phonon, as we have briefly discussed in the previous chapter in Sec. 4.1.

<span id="page-93-0"></span>limit  $ql_B \gg 1$ . In this limit, the spin-wave dispersion tends to a finite value that

<span id="page-94-0"></span>![](images/_page_94_Picture_0.jpeg)

 $\frac{E_C}{N_{el}} \sim \nu \frac{e^2}{\epsilon l_B} \frac{d}{l_B},$ 

per particle in the charge-imbalenced state, in agreement with a more sophisticated microscopic calculation [87]. In terms of the pseudo-spin magnetisation, this means that in the ground-state configuration, with a homogeneous charge distribution over both layers, all pseudo-spins are oriented in the xy-plane. Remember that a pseudo-spin  $\uparrow$  corresponds to an electron in the upper layer and  $\downarrow$  to one in the lower layer, and a configuration as the one described in Eq. (5.3) is therefore excluded, whereas the symmetric and anti-symmetric combinations

 $\chi_{+} = \bigotimes_{j=1}^{N} |+_{j}\rangle$  and  $\chi_{-} = \bigotimes_{j=1}^{N} |-_{j}\rangle$ ,

with  $|\pm_j\rangle = (|\uparrow_j\rangle \pm |\downarrow_j\rangle)/\sqrt{2}$  is not. These two states, which correspond to a ferromagnet in the x- and the y-direction, respectively, may be generalised by

 $\chi_{\phi} = \bigotimes_{j=1}^{N} |\phi_{j}\rangle,$ 

where  $|\phi_j\rangle \equiv [|\uparrow\rangle + \exp(i\phi)|\downarrow\rangle]/\sqrt{2}$ . The states  $\chi_+$  and  $\chi_-$  are obtained for

Contrary to the case of the spin ferromagnet with full SU(2) symmetry, where a general state would be described in terms of two angles  $\theta$  and  $\phi$ , the different possible easy-plane pseudo-spin ferromagnetic are characterised by the angle  $\phi$  which may vary between 0 and  $2\pi$ . The low-energy degrees of freedom

<span id="page-94-1"></span><sup>5</sup> Naturally, such an anti-symmetric orbital wave function is only physical if the layer separation d is not too large (as compared to the magnetic length) – otherwise one would

(5.5)

choosing any other direction described by the angle  $\phi$  in the xy-plane,

 $\phi = 0$  and  $\phi = \pi$  (modulo  $2\pi$ ), respectively.

simply have completely decoupled layers.

<span id="page-95-0"></span>![](images/_page_95_Picture_0.jpeg)

The State at ν = 1 97

are therefore described by a different universality class that turns out to be the same as the one that describes superfluidity or superconductivity. The relation between superfluidity and the easy-plane pseudo-spin ferromagnet in bilayer systems at ν = 1 may indeed be understood in the following manner: on the average, the average filling factor per layer is ν<sup>↑</sup> = ν<sup>↓</sup> = 1/2 in order to minimise the charging energy due to the capacitive term, i.e. there are as many electrons as holes in the LLL of each layer. Naturally, because of the Coulomb interaction between the particles in the two different layers, an electron in one layer wants to be bound to a hole in the other one. Since the number of electrons in each layer equals, on the average, that of holes in the other one, all particles find their appropriate partner in the opposite layer. The electron-hole pair in the two layers may be viewed as a charge-neutral interlayer exciton that satisfies bosonic statistics Fig. [5.2\(a)]. Below a certain temperature, these bosons condense into a collective state that is nothing other than the exciton superfluid \[88, 89, 90, [87\]](#page-118-12). The phase coherence between the different excitons is precisely described by the angle φ.

The first experimental indication of excitonic superfluidity in bilayer quantum Hall systems was a zero-bias anomaly in tunneling experiments [\[91\]](#page-118-16). Indeed, if one injects a charge in a tunneling experiment into one of the layers and collects it in a contact at the other layer, the tunneling conductance dIz/dV is expected to be weak in the case of uncorrelated electrons because of the Coulomb repulsion between electrons in the opposite layers. However, below a critical value of d/lB, where one expects the interlayer correlations to be sufficiently strong to form a phase-coherent excitonic condensate, the injected electron systematically finds a hole in the other layer, such that tunneling between the layers is strongly enhanced. This strong enhancement, which due to its reminiscence with the Josephson effect in superconductors [\[66\]](#page-117-12) is also called quasi-Josephson effect, 6 has indeed been observed experimentally [\[91\]](#page-118-16).

Another strong indication for excitons in bilayer quantum Hall systems stems from transport measurements in the counterflow configuration, where the current in the upper layer I<sup>↑</sup> = I flows in the opposite direction as compared to that in the lower layer I<sup>↓</sup> = −I see Fig. [5.2\(a)]. From a technical point of view, it is indeed possible to contact the two layers separately such that one may measure the Hall resistance (and also the longitudinal resistance) in both layers independently. In the case of exciton condensation, the charges involved in transport are zero because the excitons are charge-neutral objects, which are not coupled to the magnetic field and thus not affected by the Lorentz force. In addition to a vanishing longitudinal resistance, one would therefore expect a vanishing Hall resistance because no density gradient between opposite edges is built up to compensate the Lorentz force \[89, [90\]](#page-118-15). This is schematically shown in Fig. 5.2\(b). The simultaneous vanishing of the Hall and longitudinal resistances was indeed observed in 2004 by two different experimental groups \[92, [93\]](#page-118-18).

<span id="page-96-0"></span><sup>6</sup>Contrary to the Josephson effect, only the tunneling conductance dIz/dV is strongly enhanced whereas the tunneling current remains zero in the quasi-Josephson effect in bilayer systems.

#### <span id="page-97-0"></span>5.2.3 SU(4) ferromagnetism in graphene

The arguments in favour of a quantum Hall ferromagnetism may easily be generalised to the case of graphene, where the Coulomb interaction respects to great accuracy the four-fold spin-valley degeneracy, as we have described above. In order to avoid confusion about the filling factor, one first needs to remember that the filling factor  $\nu_G$  in graphene is defined with respect to the charge-neutral point, which happens to be in the centre of the central n=0 LL (see Sec. 3.5). Two of the four (degenerate) spin-valley branches are therefore completely filled at  $\nu_G=0$ , which in non-relativistic quantum Hall systems would correspond rather to a filling factor  $\nu=2$ . Similarly the filling factor  $\nu=1$  would correspond to a graphene filling factor  $\nu_G=-1$ , whereas  $\nu_G=1$  implies three completely filled spin-valley branches ( $\nu=3$ ).

Let us first consider the filling factor  $\nu_G = -1$  and see how the above considerations apply to graphene with its SU(4) symmetry.<sup>7</sup> In the same manner as for the spin quantum Hall ferromagnet at  $\nu = 1$ , the short-range component  $v_0$  of the Coulomb potential is screened in the completely anti-symmetric orbital wave function (4.7), and the spin part of the wave function must therefore be completely symmetric. Notice, however, that one may now distribute the electron over the four internal states  $|m; K, \uparrow\rangle$ ,  $|m; K, \downarrow\rangle$ ,  $|m; K', \uparrow\rangle$  and  $|m; K', \downarrow\rangle$ . The general spin wave function is therefore a superposition of all these states

$$\chi_{\mathrm{SU}(4)} = \bigotimes_{m=1}^{N} \left( u_{m,1} | m; K, \uparrow \rangle + u_{m,2} | m; K, \downarrow \rangle + u_{m,3} | m; K', \uparrow \rangle + u_{m,4} | m; K', \downarrow \rangle \right),$$

where the complex coefficients  $u_{m,i}$  satisfy the normalisation condition  $\sum_{i=1}^{4} |u_{m,i}|^2 = 1$ . In the case of global coherence, all coefficients are independent of the guiding-centre quantum number m,  $u_{m,i} = u_i$ , and one thus obtains the spin wave function of an SU(4) ferromagnetism [94, 95, 96, 97]. These arguments may also be generalised to the case of  $\nu_G = 0$ , where two branches are completely filled [97], but the ground state does not reveal the same degeneracy as the SU(4) ferromagnet at  $\nu_G = \pm 1$ . Indeed, a general argument on K-component quantum Hall system shows that one has generalised ferromagnetic states at all integer values of the filling factor  $\nu = 1, ..., K-1$  [98].

As a consequence of the SU(4) quantum Hall ferromagnet, one may expect a quantum Hall effect in graphene at the unusual filling factors  $\nu_G = 0, \pm 1$ . Remember that these states do not belong to the series (3.22),  $\nu_G = \pm 2, \pm 4, ...$  of the RQHE which may be explained by LL quantisation within the picture of non-interacting relativistic particles. In the same manner as for the spin quantum Hall ferromagnet, the gapless spin-density-wave modes, which reveal a higher degeneracy due to the larger SU(4) symmetry, do not imply that the charged modes are also gapless. Indeed, the elementary charged excitations of the SU(4) quantum Hall ferromagnet are generalised skyrmions [97, 99] which are separated by a gap from the ground state, which therefore describes an

<span id="page-97-1"></span>The filling factor  $\nu_G = 1$  is related to  $\nu_G = -1$  by particle-hole symmetry and therefore does not require a separate discussion.

incompressible quantum liquid that displays the quantum Hall effect. A quantum Hall effect has indeed been observed at these unusual filling factors [22], in agreement with the formation of an SU(4) quantum Hall ferromagnet. However, there exist alternative scenarios to describe the appearance of a quantum Hall effect at these filling factors [100, 101, 102] and a clear indication of SU(4) quantum Hall ferromagnetism is yet lacking.

We finally emphasise that an SU(4) description is not restricted to graphene. Indeed, if one takes into account the electron spin, the bilayer quantum Hall system and its excitations may also be treated within the SU(4) framework [98, 103, 3, 99] although the interaction does not respect the full SU(4) symmetry because of the asymmetry in the layer pseudo-spin described above.

#### <span id="page-98-0"></span>5.3 Multi-Component Wave Functions

Until now, we have considered a multi-component quantum Hall effect at the integer filling factor  $\nu=1$  (or other integer fillings in the case of graphene) that is described in terms of the Vandermonde determinant (4.7)  $\prod_{k< l} (z_k-z_l)$  regardless of whether the particle at the position  $z_k$  is in a state  $\uparrow$  or  $\downarrow$ . The spin orientation has only been taken into account within a spin wave function that is multiplied to the Vandermonde determinant. One may naturally ask the question whether one may also describe other filling factors than  $\nu=1$ .

A simple generalisation of the quantum Hall ferromagnetism to other filling factors consists of replacing the Vandermonde determinant by, e.g., the Laughlin (4.3) at  $\nu=1/(2s+1)$  or the Jain wave function (4.30) at  $\nu=p/(2sp+1)$  and to multiply it again with a spin wave function that is naturally ferromagnetic because the orbital wave function remains anti-symmetric. There are, however, more general states for which the orbital wave function is not fully anti-symmetric, but only in the intra-component parts as it is required by the Pauli principle. These states are described in terms of wave functions proposed by Halperin in 1983 [84] that we present in this section, as well as a natural generalisation to systems with more components than K=2.

#### <span id="page-98-1"></span>5.3.1 Halperin's wave function

Halperin's wave function for spin-1/2 electrons is a straight-forward generalisation of Laughlin's proposal (4.3). We consider the particle positions to be separated into two sets  $\{z_1^{\uparrow}, z_2^{\uparrow}, ..., z_{N_{\uparrow}}^{\uparrow}\}$  for spin- $\uparrow$  particles and  $\{z_1^{\downarrow}, z_2^{\downarrow}, ..., z_{N_{\downarrow}}^{\downarrow}\}$  for spin- $\downarrow$  particles. If the particles with different spin orientation could be treated as independent from one another, i.e. in the absence of an interaction between spin- $\uparrow$  and spin- $\downarrow$  particles, one would simply write down a product ansatz

<span id="page-98-2"></span>
$$\psi_{\uparrow,m_1}^L(\{z_j^{\uparrow}\}) \times \psi_{\downarrow,m_2}^L(\{z_j^{\downarrow}\}) = \prod_{k < l}^{N_{\uparrow}} \left(z_k^{\uparrow} - z_l^{\uparrow}\right)^{m_1} \prod_{k < l}^{N_{\downarrow}} \left(z_k^{\downarrow} - z_l^{\downarrow}\right)^{m_2} \tag{5.7}$$

of two independent Laughlin wave functions that need not necessarily be described by the same exponent m. The total filling factor would then be simply the sum  $\nu = \nu_{\uparrow} + \nu_{\downarrow}$  of the filling factors  $\nu_{\uparrow} = 1/m_1$  and  $\nu_{\downarrow} = 1/m_2$  for spin- $\uparrow$  and spin- $\downarrow$  particles, respectively.

Apart from the fact that this situation is not particularly interesting, it is also unphysical because the Coulomb interaction does not depend on the spin orientation of the particle pairs. In the wave function (5.7), two particles of opposite spin orientation may be at the same position, i.e. the wave function does not vanish in general for  $z_k^{\uparrow} = z_l^{\downarrow}$ . Remember that such a double occupancy of the same position would be penalised by an energy cost on the order of the short-range component  $v_0$  in a pseudopotential expansion.

In order to account for these inter-component correlations, Halperin proposed to add a factor  $\prod_{k=1}^{N_{\uparrow}}\prod_{l=1}^{N_{\downarrow}}(z_{k}^{\uparrow}-z_{l}^{\downarrow})^{n}$  to the wave function (5.7) the exponent of which does not necessarily need to be odd because particles of opposite spin orientation are not constrained by the Pauli principle. Halperin's wave function

<span id="page-99-0"></span>
$$\psi_{m_1, m_2, n}^{H}(\{z_j^{\uparrow}, z_j^{\downarrow}\}) = \prod_{k < l}^{N_{\uparrow}} \left(z_k^{\uparrow} - z_l^{\uparrow}\right)^{m_1} \prod_{k < l}^{N_{\downarrow}} \left(z_k^{\downarrow} - z_l^{\downarrow}\right)^{m_2} \prod_{k = 1}^{N_{\uparrow}} \prod_{l = 1}^{N_{\downarrow}} \left(z_k^{\uparrow} - z_l^{\downarrow}\right)^{n} \tag{5.8}$$

is therefore characterised by the set  $(m_1, m_2, n)$  of three exponents.

In analogy with Laughlin's wave function, for which we have  $\nu=1/m$ , the exponents fix the (component) filling factors, as one may see from the power-counting argument (see Sec. 4.2). According to this argument, the maximal exponent for a particular particle position cannot exceed the number of flux quanta  $N_B$  threading the area  $\mathcal{A}$  of the 2D electron system. Apart from the shift that vanishes anyway in the thermodynamic limit, one obtains the two equations

<span id="page-99-1"></span>
$$N_B = m_1 N_{\uparrow} + n N_{\downarrow}$$
 and  $N_B = m_2 N_{\downarrow} + n N_{\uparrow}$ . (5.9)

This means that, contrary to the simpler case of Laughlin's wave function, the number of zeros in one component is not simply given by the corresponding exponent times the number of particles in this component (first term in the above expressions). Instead, it is also affected by the particles in the other component that contribute each a zero of order n (second term) due to the mixed term in Halperin's wave function (5.8). In terms of the component filling factors,

$$\nu_{\sigma} = \frac{N_{\sigma}}{N_{B}},\tag{5.10}$$

Eq. (5.9) may be rewritten in matrix form

<span id="page-99-3"></span>
$$\begin{pmatrix} 1 \\ 1 \end{pmatrix} = \begin{pmatrix} m_1 & n \\ n & m_2 \end{pmatrix} \begin{pmatrix} \nu_{\uparrow} \\ \nu_{\downarrow} \end{pmatrix}, \tag{5.11}$$

from which one obtains the component filling factors by matrix inversion

<span id="page-99-2"></span>
$$\begin{pmatrix} \nu_{\uparrow} \\ \nu_{\downarrow} \end{pmatrix} = \frac{1}{m_1 m_2 - n^2} \begin{pmatrix} m_2 & -n \\ -n & m_1 \end{pmatrix} \begin{pmatrix} 1 \\ 1 \end{pmatrix}, \tag{5.12}$$

and one finds

<span id="page-100-0"></span>
$$\nu = \nu_{\uparrow} + \nu_{\downarrow} = \frac{m_1 + m_2 - 2n}{m_1 m_2 - n^2}$$
 (5.13)

for the total filling factor.

One first notices that, in Eq. \(5.12\), not only the filling factors are fixed by the exponents but also, for a given magnetic field (i.e. a given number of flux quanta), the number of particles per component. Contrary to what one could have expected from the expression of Halperin's wave function \(5.8\), the numbers Nσ, namely the ratio between them, cannot be chosen arbitrarily.

Furthermore, the above expressions \(5.12\) and \(5.13\) for the filling factors are ill-defined if the exponent matrix in Eq. \(5.11\) is not invertible, i.e. when its determinant is zero, m1m<sup>2</sup> − n <sup>2</sup> = 0. The only physically relevant situation arises when all exponents are equal odd integers m<sup>1</sup> = m<sup>2</sup> = n. However, this result should not surprise us: we are then confronted again with a completely anti-symmetric wave function, actually a Laughlin wave function, which requires a ferromagnetic spin wave function. As we have seen above, in the discussion of the quantum Hall ferromagnetism, the ground-state manifold comprises states with different polarisation along the z-axis: the state with N<sup>↑</sup> = N and N<sup>↓</sup> = 0 is an equally valid ground state as a state with N<sup>↑</sup> = N<sup>↓</sup> = N/2 or N<sup>↑</sup> = 0 and N<sup>↓</sup> = N, where N = N<sup>↑</sup> + N<sup>↓</sup> is the total number of particles. The component filling factor is therefore not well-defined and depends on the polarisation

$$p_z = \frac{N_{\uparrow} - N_{\downarrow}}{N} = \frac{\nu_{\uparrow} - \nu_{\downarrow}}{\nu},\tag{5.14}$$

whereas the total filling factor is simply given by ν = 1/m, in terms of the common odd exponent m. Notice that contrary to the quantum Hall ferromagnet, a state with an invertible exponent matrix has a polarisation that is completely fixed,

$$p_z = \frac{m_2 - m_1}{m_1 m_2 - n^2} \ . \tag{5.15}$$

We finally mention that not all states that can be written down in terms of Halperin's wave function are good candidates for the description of the ground state chosen by the system. One may show, e.g. within a generalisation of Laughlin's plasma analogy (presented in Sec. 4.2.5\) to two or more components, that several of Halperin's wave functions do not describe a homogeneous liquid but a liquid in which the different components phase-separate [\[104\]](#page-119-6). For two components, the condition for a homogeneous state is simply that both the exponents m<sup>1</sup> and m2, which describe the intra-component correlations, must be larger than n for the inter-component correlations. As an example, we may study the states (3, 3, 1) and (1, 1, 3), which would both be candidates for a possible two-component FQHE at ν = 1/2 and which have indeed been investigated in the literature [\[105\]](#page-119-7). However, only the first one describes a homogeneous liquid, such that the second one may be discarded right from the beginning.

Furthermore, some of Halperin's wave functions, even if they satisfy the above-mentioned condition, turn out to be problematic if the interaction is SU(2) symmetric, such as for the true electron spin. In this case, one may show that (m, m, n) states are only eigenstates of the total-spin operator, which commutes with the interaction Hamiltonian, if n = m (i.e. in the ferromagnetic state) or if n = m − 1 [\[1\]](#page-114-0). This restriction may be omitted though in bilayer quantum Hall systems or in wide quantum wells where the interaction Hamiltonian is not pseudo-spin SU(2)-symmetric.

#### Physical relevance of Halperin states

A physically relevant Halperin state is e.g. the unpolarised (3, 3, 2) state which would occur at a filling factor ν = 2/5. Remember from the discussion of CF theory in Sec. 4.4 that there is also a (naturally polarised) CF candidate, with p = 2 completely filled CF LLs, to describe the ground state at this filling factor. Which of them is now the better one? This question could be answered within exact-diagonalisation calculations, which showed that, in the absence of a Zeeman effect, the true ground state is described in terms of the unpolarised Halperin wave function (3, 3, 2) [\[106\]](#page-119-8). Notice, however, that the energy difference between the two states is extremely small, as may be seen from variational calculations [\[76\]](#page-118-1), such that the polarised CF state becomes the ground state above a critical value of the energy ∆<sup>Z</sup> associated with the Zeeman effect. This critical value would therefore describe a phase transition between an unpolarised and a fully polarised FQHE state. Such transitions have indeed been observed in polarisation experiments, where the strength of the Zeeman effect was varied by a simultaneous change in the magnetic field and in the electronic density \[107, [108\]](#page-119-10).

#### <span id="page-101-0"></span>5.3.2 Generalised Halperin wave functions

We would finally mention that Halperin's wave function may easily be generalised to describe possible FQHE states in systems with a larger number of components, such as the four spin-valley components in graphene. This generalised wave function for K-component quantum Hall systems may be written as a product

<span id="page-101-1"></span>
$$\psi_{m_1,...,m_K;n_{ij}}^{SU(K)} \left( \left\{ z_{j_1}^{(1)}, z_{j_2}^{(2)}, ..., z_{j_K}^{(K)} \right\} \right) = \psi_{m_1,...,m_K}^L \times \psi_{n_{ij}}^{inter}$$
 (5.16)

of a product of Laughlin wave functions

$$\psi_{m_1,...,m_K}^L = \prod_{j=1}^K \prod_{k_j < l_j} \left( z_{k_j}^{(j)} - z_{l_j}^{(j)} \right)^{m_j}$$

for each of the components and a term

$$\psi_{n_{ij}}^{inter} = \prod_{i < j}^{K} \prod_{k_i}^{N_i} \prod_{k_j}^{N_j} \left( z_{k_i}^{(i)} - z_{k_j}^{(j)} \right)^{n_{ij}}$$

that takes into account the correlations between particles in different components [109]. Here, the indices i and j denote the component, i, j = 1, ..., K, and  $z_{k_i}^{(i)}$  is the complex position of the  $k_i$ -th particle in the component i.

Although the wave function (5.16) may seem scary at the first sight, it is as easily manipulated as Halperin's original wave function (5.8). The component filling factors  $\nu_j = N_j/N_B$  may be determined, in the same manner as in the two-component case (5.11), with the help of the "exponent matrix"  $\mathcal{M}$  the off-diagonal terms of which are the exponents  $(\mathcal{M})_{ij} = n_{ij}$  (for  $i \neq j$ ), whereas the diagonal terms are simply the exponents corresponding to the intra-component correlations,  $(\mathcal{M})_{ii} = m_i$ . The zero-counting argument yields the matrix equation

<span id="page-102-0"></span>
$$\begin{pmatrix} 1 \\ \vdots \\ 1 \end{pmatrix} = \mathcal{M} \begin{pmatrix} \nu_1 \\ \vdots \\ \nu_K \end{pmatrix} \tag{5.17}$$

relating the component filling factors to the exponents, and if  $\mathcal{M}$  is invertible, all component filling factors are fixed by the inverse equation

<span id="page-102-1"></span>
$$\begin{pmatrix} \nu_1 \\ \vdots \\ \nu_K \end{pmatrix} = \mathcal{M}^{-1} \begin{pmatrix} 1 \\ \vdots \\ 1 \end{pmatrix}. \tag{5.18}$$

If the determinant  $\det(\mathcal{M})$  is zero and the matrix thus not invertible, not all component filling factors can be determined. In analogy with the two-component case this hints at underlying ferromagnetic states. A perfect  $\mathrm{SU}(K)$  ferromagnetic state is obtained when all components are equal odd integers,  $m_i = n_{ij} = m$ , in which case one obtains again a simple (fully anti-symmetric) Laughlin wave function for all particles regardless of to which component they belong. For K=4 and m=1, this is just the  $\mathrm{SU}(4)$  ferromagnetic state at  $\nu=1$  which we have already discussed in the context of the quantum Hall effect at  $\nu_G=\pm 1$  in graphene (Sec. 5.2.3).

Notice, however, that contrary to a two-component system, where one only needs to distinguish between an invertible and a non-invertible matrix, the situation is much richer for K > 2. One may indeed have different "degrees" of invertibility that are described by the rank of the matrix. Consider, e.g., the fully anti-symmetric wave function with  $m_i = n_{ij} = m$ . In this case, Eq. (5.17) actually consists only of one single equation relating the component filling factors, i.e.  $1 = m(\nu_1 + ... + \nu_K) = m\nu$ , and all other lines of the matrix equation are simply copies of the first one. The rank of this matrix is 1, i.e. only the total filling factor is fixed,  $\nu = 1/m$  [SU(K) ferromagnet] whereas in the case of an invertible matrix the rank is K and the K lines in the matrix equation (5.17) represent (linearly) independent equations. If the rank of an exponent matrix is smaller than K but larger than 1, the resulting state is neither a full SU(K) ferromagnet nor a state with completely fixed component filling factors (or polarisations) – it is rather a state with some intermediate ferromagnetic properties.

As for two-component Halperin wave functions \(5.8\), a generalisation of Laughlin's plasma analogy allows one to distinguish between physical (i.e. homogeneous) and unphysical states (which show a phase separation of at least some of the components). Indeed, the exponent matrix M must have only positive eigenvalues in order to describe a homogeneous state [\[104\]](#page-119-6). We finally mention that M encodes not only information concerning the filling factors \(5.18\), but fully describes the quantum Hall state \(5.16\), such as its topological degeneracy, the charges of its quasi-particle excitations as well as the statistical properties of the latter [\[110\]](#page-119-12).

<span id="page-104-0"></span>![](images/_page_104_Picture_0.jpeg)

<span id="page-104-3"></span><span id="page-104-2"></span> $H\psi_{\mathbf{k}}=\epsilon_{\mathbf{k}}\psi_{\mathbf{k}},$  where H is the full Hamiltonian for electrons on a lattice, which is of the type (2.2) mentioned in Sec. 2.1. Here, we have chosen an arbitrary representation, which is not necessarily that in real space. Multiplication of the Schrödinger equation by  $\psi_{\mathbf{k}}^*$  from the left yields the equation  $\psi_{\mathbf{k}}^*H\psi_{\mathbf{k}}=\epsilon_{\mathbf{k}}\psi_{\mathbf{k}}^*\psi_{\mathbf{k}}$ , which may

<span id="page-104-1"></span><sup>1</sup>The wavefunction  $\psi_{\mathbf{k}}(\mathbf{r})$  is, thus, the real space representation of the Hilbert vector  $\psi_{\mathbf{k}}$ .

105

![](images/_page_105_Picture_0.jpeg)

<span id="page-105-3"></span><span id="page-105-2"></span><span id="page-105-1"></span> $\mathcal{S}_{\mathbf{k}} \equiv \begin{pmatrix} \psi_{\mathbf{k}}^{(A)*} \psi_{\mathbf{k}}^{(A)} & \psi_{\mathbf{k}}^{(A)*} \psi_{\mathbf{k}}^{(B)} \\ \psi_{\mathbf{k}}^{(B)*} \psi_{\mathbf{k}}^{(A)} & \psi_{\mathbf{k}}^{(B)*} \psi_{\mathbf{k}}^{(B)} \end{pmatrix} = \mathcal{S}_{\mathbf{k}}^{\dagger}$ 

accounts for the non-orthogonality of the trial wavefunctions. The eigenvalues  $\epsilon_{\mathbf{k}}$  of the Schrödinger equation yield the energy bands, and they may be obtained

<span id="page-105-0"></span> $\det \left[ \mathcal{H}_{\mathbf{k}} - \epsilon_{\mathbf{k}}^{\lambda} \mathcal{S}_{\mathbf{k}} \right] = 0,$ 

which needs to be satisfied for a non-zero solution of the wavefunctions, i.e. for  $a_{\mathbf{k}} \neq 0$  and  $b_{\mathbf{k}} \neq 0$ . The label  $\lambda$  denotes the energy bands, and it is clear that there are as many energy bands as solutions of the secular equation (A.6), i.e.

From now on, we neglect the overlap of wave functions on neighbouring sites, such that the overlap matrix (A.5) simply becomes the one matrix 1 times the number of particles N due to the normalisation of the wave functions. The secular equation then tells us that the energy bands are just the eigenvalues of the Hamiltonian matrix (A.4). Furthermore, one notices that because the two sublattices are equivalent from a chemical point of view, we have  $\psi_{\mathbf{k}}^{(A)*}H\psi_{\mathbf{k}}^{(A)}=$  $\psi_{\mathbf{k}}^{(B)*}H\psi_{\mathbf{k}}^{(B)}$ , and the diagonal terms therefore contribute just a constant shift

and the overlap matrix

from the secular equation

two bands for the case of two atoms per unit cell.

(A.4)

(A.5)

(A.6)

<span id="page-106-1"></span>![](images/_page_106_Picture_0.jpeg)

The sites  $B_1$  and  $B_2$  correspond to lattice vectors shifted by

 $\mathbf{a}_2 = \frac{\sqrt{3}a}{2}(\mathbf{e}_x + \sqrt{3}\mathbf{e}_y)$  and  $\mathbf{a}_3 \equiv \mathbf{a}_2 - \mathbf{a}_1 = \frac{\sqrt{3}a}{2}(-\mathbf{e}_x + \sqrt{3}\mathbf{e}_y),$ 

respectively, where  $a = |\boldsymbol{\delta}_3| = 0.142$  nm is the distance between nearest-neighbour carbon atoms. Therefore, they contribute a phase factor  $\exp(i\mathbf{k} \cdot \mathbf{a}_2)$  and  $\exp(i\mathbf{k} \cdot \mathbf{a}_3)$ , respectively. The hopping term (A.7) may therefore be written

 $t_{\mathbf{k}}^{AB} = t \gamma_{\mathbf{k}}^* = \left( t_{\mathbf{k}}^{BA} \right)^*,$ 

<span id="page-106-0"></span> $\gamma_{\mathbf{k}} \equiv 1 + e^{i\mathbf{k}\cdot\mathbf{a}_2} + e^{i\mathbf{k}\cdot\mathbf{a}_3}$ 

 $\epsilon_{\lambda}(\mathbf{k}) = \lambda |t_{\mathbf{k}}^{AB}| = \lambda t |\gamma_{\mathbf{k}}|,$ 

and is plotted in Fig. 2.2. The band dispersion is obviously particle-hole symmetric, and the valence band ( $\lambda = -$ ) touches the conduction band ( $\lambda$ ) in the

 $\pm \mathbf{K} = \pm \frac{4\pi}{3\sqrt{3}a} \mathbf{e}_x \; ,$ 

The band dispersion may now easily be obtained by solving the secular

(A.9)

(A.10)

where we have defined the sum of the nearest-neighbour phase factors

equation (A.6),

inequivalent points

 $H_D = v\mathbf{p} \cdot \boldsymbol{\sigma}$ ,

<span id="page-107-0"></span> $H'_D = -v\mathbf{p}\cdot\boldsymbol{\sigma}^*$ ,

with  $\sigma^* = (\sigma^x, -\sigma^y)$ . Both Hamiltonians yield the same energy spectrum which

whereas the low-energy Hamiltonian at the K' point reads

is therefore two-fold valley-degenerate.

(A.14)

(A.15)

<span id="page-108-0"></span>![](images/_page_108_Picture_0.jpeg)

![](images/_page_109_Picture_0.jpeg)

# <span id="page-110-0"></span>Appendix B

# Landau Levels of Massive Dirac Particles

## Mass Confinement of Dirac Fermions at B = 0

Even in the absence of a magnetic field, electronic confinement in graphene turns out to be quite tricky because a simple-minded approach in terms of a potential Vconf = V (y)<sup>1</sup> cannot confine Dirac electrons. This fact is due to an intrinsically relativistic effect that is called the Klein paradox, according to which a (massless) relativistic particle may transverse a potential barrier without being backscattered [\[112\]](#page-119-14). This effect may be understood in the following manner: consider an incident electron in the region with V = 0 the energy of which is slightly above the Fermi energy. In the potential barrier, the Dirac point is shifted to a higher energy that corresponds to the barrier height and the Fermi energy lies now in the valence band, where the electron may still find a quantum state (with the same wave-vector direction and the same velocity v) – instead of moving as an electron in the conduction band, it thus simply moves in the same direction as an electron in the valence band Fig. [B.1\(a)]. This is in stark contrast with quantum mechanical tunneling of a non-relativistic particle, for which the transmission probability through a potential barrier is exponentially suppressed because of a lacking quantum state at the same energy as that of the incident electron.

The problem is circumvented by a so-called mass confinement

$$V_{\text{conf}} = V(y) \,\sigma^z = \begin{pmatrix} V(y) & 0\\ 0 & -V(y) \end{pmatrix}, \tag{B.1}$$

and we discuss first the simpler case of a constant mass term Mσ<sup>z</sup> that needs to be added to the Dirac Hamiltonian. That this term yields indeed a mass may be seen from the Dirac Hamiltonian at B = 0

<span id="page-110-1"></span>
$$H_D^m = v\mathbf{p} \cdot \boldsymbol{\sigma} + M\sigma^z = \begin{pmatrix} M & v(p_x - ip_y) \\ v(p_x + ip_y) & -M \end{pmatrix},$$
 (B.2)

![](images/_page_111_Picture_2.jpeg)

Figure B.1: (a) Klein tunneling through a barrier. An incident electron in the conduction band (CB) above the Fermi energy, which is at the Dirac point before the barrier, transverses the barrier as en electron above the Fermi energy in the valence band (VB). The valence band is partially emptied because the Dirac point has shifted to a higher energy corresponding to the barrier height. (b) Mass confinement. A gap opens when the particle approaches the edge, which becomes a forbidden region where no quantum state can be found at the energy corresponding to that of the incident electron.

<span id="page-111-0"></span>the diagonalisation of which yields the energy spectrum

$$\epsilon_{\lambda}(\mathbf{p}) = \lambda \sqrt{v^2 |\mathbf{p}|^2 + M^2},$$

which is gapped at zero momentum. This is nothing other than the dispersion relation of a relativistic particle1 with mass m such that M = mv<sup>2</sup> . Qualitatively one may see from Fig. B.1\(b) why a mass confinement is more efficient than a potential barrier. Indeed, when the particle approaches the edge with M(y) 6= 0 a gap opens. An electron slightly above the Dirac point may then only propagate in the region with M = 0, whereas at the edge its energy lies in the gap which is a forbidden region, and the electron is thus confined.

Similarly to the B = 0 case, one may find the energy spectrum of the massive Dirac Hamiltonian \(B.2\) in a perpendicular magnetic field, which reads, in terms of the ladder operators a and a † ,

<span id="page-111-2"></span>
$$H_D^B = \left( \begin{array}{cc} M & v(\Pi_x - i\Pi_y) \\ v(\Pi_x + i\Pi_y) & -M \end{array} \right) = \left( \begin{array}{cc} M & \sqrt{2} \frac{\hbar v}{l_B} a \\ \sqrt{2} \frac{\hbar v}{l_B} a^\dagger & -M \end{array} \right). \tag{B.3}$$

Its eigenvalues may be obtained in the same manner as in the M = 0 case (c.f. Sec. 2.3.2\), and one obtains

<span id="page-111-3"></span>
$$\epsilon_{\lambda n} = \lambda \sqrt{M^2 + 2\frac{\hbar^2 v^2}{l_B^2} n} \tag{B.4}$$

<span id="page-111-1"></span><sup>1</sup> The sign λ = − corresponds to the anti-particle.

for the massive relativistic LLs,  $n \neq 0$ .

Special care needs to be taken in the discussion of the central LL n = 0, which necessarily shifts away from zero energy. The associated quantum state (2.24) is zero in the first component  $u_0$ , whereas the second component is given by  $v_0 = |0\rangle$ . In order to satisfy the second line in the eigenvalue equation

$$H_D^B \psi_0 = \epsilon_0 \psi_0 \qquad \Leftrightarrow \qquad \left( \begin{array}{cc} M & \sqrt{2} \frac{\hbar v}{l_B} a \\ \sqrt{2} \frac{\hbar v}{l_B} a^\dagger & -M \end{array} \right) \left( \begin{array}{c} 0 \\ |0\rangle \end{array} \right) = \epsilon_0 \left( \begin{array}{c} 0 \\ |0\rangle \end{array} \right),$$

one needs to fulfil

<span id="page-112-0"></span>
$$\sqrt{2}\frac{\hbar v}{l_B} a^{\dagger} u_0 = (\epsilon_0 + M)v_0 \qquad \Leftrightarrow \qquad 0 = (\epsilon_0 + M)|0\rangle, \tag{B.5}$$

such that the only solution is  $\epsilon_0 = -M$ . The relativistic n = 0 LL is therefore shifted to negative energies and does no longer satisfy particle-hole symmetry. This effect is called *parity anomaly* and depends on the sign of the mass.

In the case of graphene, we need to remember that there are two copies of the energy spectrum, one at the K point and one at the K' point. As we have disussed in Appendix A, the Hamiltonian (B.3) describes the low-energy properties at the K point whereas we need to interchange the A and B sublattices at the K' point and add a global sign in front of the off-diagonal terms [see Eq. (A.16)],

$$H_D^{B\prime} = \begin{pmatrix} -M & -\sqrt{2}\frac{\hbar v}{l_B}a \\ -\sqrt{2}\frac{\hbar v}{l_B}a^{\dagger} & M \end{pmatrix} = -H_D^{B\prime}.$$
 (B.6)

Naturally, the eigenstates of this Hamiltonian are the same as those of the Hamiltonian (B.3) at the K point, but the eigenvalues change their sign. Due to the particle-hole symmetry of the levels (B.4), the global sign does not affect the energy spectrum for  $n \neq 0$ . However, the n = 0 LL, which does not respect particle-hole symmetry, must again be treated apart, and one finds in the same manner as for the K point the condition corresponding to Eq. (B.5),

$$-\sqrt{2}\frac{\hbar v}{l_B}a^{\dagger}u_0 = (\epsilon_0 - M)v_0 \qquad \Leftrightarrow \qquad 0 = (\epsilon_0 - M)|0\rangle. \tag{B.7}$$

One notices that the n=0 LL level at the K' point shifts to positive energies as a function of the mass, such that the overall level spectrum for graphene, when one takes into account both valleys, is again particle-hole symmetric, but the valley degeneracy is lifted for n=0.

The case of a mass term that varies in the y-direction, such as for the mass confinement potential, may finally be treated in the same manner as we have discussed in Sec. 3.1.2: the system remains translation-invariant in the x-direction, such that the Landau gauge is the appropriate gauge and the wave vector k in this direction is a good quantum number. Because this wave vector determines

the position of the eigenstate in the y-direction,  $y_0 = k l_B^2$ , the energy spectrum is given by the expression (3.21),

<span id="page-113-0"></span>
$$\epsilon_{\lambda n, y_0; \xi} = \lambda \sqrt{M^2(y_0) + 2\frac{\hbar^2 v^2}{l_B^2} n}, \tag{B.8}$$

for  $n \neq 0$  and both valleys  $\xi = \pm,$  whereas the n = 0 LL is found at

$$\epsilon_{n=0,y_0;\xi} = -\xi M(y_0).$$
 (B.9)

- <span id="page-114-0"></span>[1] Prange, R. and Girvin, E., S. M. (1990) The Quantum Hall Effect. Springer.
- <span id="page-114-2"></span><span id="page-114-1"></span>[2] Yoshioka, D. (2002) The Quantum Hall Effect. Springer.
- [3] Ezawa, Z. F. (2000) Quantum Hall Effects Field Theoretical Approach and Related Topics. World Scientific.
- <span id="page-114-3"></span>[4] Girvin, S. M. (1999) The Quantum Hall Effect: Novel Excitations and Broken Symmetries, in A. Comptet, T. Jolicoeur, S. Ouvry and F. David (Eds.) Topological Aspects of Low-Dimensional Systems – Ecole d' ´ Ete de ´ Physique Th´eorique LXIX . Springer.
- <span id="page-114-5"></span><span id="page-114-4"></span>[5] Murthy, G. and Shankar, R. (2003) Rev. Mod. Phys., 75, 1101.
- [6] Novoselov, K. S., Geim, A. K., Morosov, S. V., Jiang, D., Katsnelson, M. I., Grigorieva, I. V., Dubonos, S. V., and Firsov, A. A. (2005) Nature, 438, 197.
- <span id="page-114-7"></span><span id="page-114-6"></span>[7] Zhang, Y., Tan, Y.-W., Stormer, H. L., and Kim, P. (2005) Nature, 438, 201.
- [8] Akkermans, E. and Montambaux, G. (2008) Mesoscopic Physics of Electrons and Photons. Cambridge UP.
- <span id="page-114-8"></span>[9] Shubnikov, L. W. and de Haas, W. J. (1930) Proceedings of the Royal Netherlands Society of Arts and Science, 33, 130 and 163.
- <span id="page-114-10"></span><span id="page-114-9"></span>[10] v. Klitzing, K., Dorda, G., and Pepper, M. (1980) Phys. Rev. Lett., 45, 494.
- <span id="page-114-11"></span>[11] Poirier, W. and Schopfer, F. (2009) Eur. Phys. J. Special Topics, 172, 207.
- <span id="page-114-12"></span>[12] Poirier, W. and Schopfer, F. (2009) Int. J. Mod. Phys. B, 23, 2779.
- [13] Tsui, D. C., St¨ormer, H., and Gossard, A. C. (1983) Phys. Rev. Lett., 48, 1559.

- <span id="page-115-1"></span><span id="page-115-0"></span>[14] Laughlin, R. B. (1983) Phys. Rev. Lett., 50, 1395.
- <span id="page-115-2"></span>[15] Jain, J. K. (1989) Phys. Rev. Lett., 63, 199.
- <span id="page-115-3"></span>[16] Jain, J. K. (1990) Phys. Rev. B, 41, 7653.
- [17] Willett, R. L., Eisenstein, J. P., Stormer, H. L., Tsui, D. C., Gossard, A. C., and English, J. H. (1987) Phys. Rev. Lett., 59, 1776.
- <span id="page-115-5"></span><span id="page-115-4"></span>[18] Moore, G. and Read, N. (1991) Nucl. Phys. B, 360, 362.
- <span id="page-115-6"></span>[19] Greiter, M., Wen, X.-G., and Wilczek, F. (1991) Phys. Rev. Lett., 66, 3205.
- [20] Pan, W., Stormer, H. L., Tsui, D. C., Pfeiffer, L. N., Baldwin, K. W., and West, K. W. (2003) Phys. Rev. Lett., 90, 016801.
- <span id="page-115-7"></span>[21] Castro Neto, A. H., Guinea, F., Peres, N. M. R., Novoselov, K. S., and Geim, A. K. (2009) Rev. Mod. Phys., 81, 109.
- <span id="page-115-8"></span>[22] Zhang, Y., Jiang, Z., Small, J. P., Purewal, M. S., Tan, Y.-W., Fazlollahi, M., Chudow, J. D., Jaszczak, J. A., Stormer, H. L., and Kim, P. (2006) Phys. Rev. Lett., 98, 197403.
- <span id="page-115-9"></span>[23] Du, X., Skachko, I., Duerr, F., Luican, A., and Andrei, E. Y. (2009) Nature, p. doi:10.1038/nature08522.
- <span id="page-115-10"></span>[24] Bolotin, K. I., Ghahari, F., Shulman, M. D., Stormer, H. L., and Kim, P. (2009) preprint, p. arXiv:0910.2763.
- <span id="page-115-12"></span><span id="page-115-11"></span>[25] Ashcroft, N. W. and Mermin, N. D. (1976) Solid State Physics. Harcourt.
- <span id="page-115-13"></span>[26] Kittel, C. (2005) Introduction to Solid State Physics. Wiley, 8th Ed.
- <span id="page-115-14"></span>[27] Jackson, J. D. (1999) Classical Electrondynamics. Wiley, 3rd ed.
- <span id="page-115-15"></span>[28] Cohen-Tannoudji, C., Diu, B., and Lalo¨e, F. (1973) Quantum Mechanics. Hermann.
- <span id="page-115-18"></span>[29] McClure, J. W. (1956) Phys. Rev., 104, 666.
- [30] Berger, C., Song, Z., Li, T., Ogbazghi, A. Y., Feng, R., Dai, Z., Marchenkov, A. N., Conrad, E. H., First, P. N., and de Heer, W. A. (2004) J. Phys. Chem., 108, 19912.
- <span id="page-115-16"></span>[31] Sadowski, M. L., Martinez, G., Potemski, M., Berger, C., and de Heer, W. A. (2006) Phys. Rev. Lett., 97, 266405.
- <span id="page-115-17"></span>[32] Jiang, Z., Henriksen, E. A., L. C. Tung, Y.-J. W., Schwartz, M. E., Han, M. Y., Kim, P., and Stormer, H. L. (2007) Phys. Rev. Lett., 98, 197403.
- <span id="page-115-19"></span>[33] Champel, T. and Florens, S. (2007) Phys. Rev. B, 75, 245326.

<span id="page-116-0"></span>[34] Abrahams, E., Anderson, P. W., Licciardello, D. C., and Ramakrishnan, T. V. (1979) Phys. Rev. Lett., 42, 673.

- <span id="page-116-1"></span>[35] B¨uttiker, M. (1992) The Quantum Hall Effect in Open Conductors, in M. Reed (Ed.) Nanostructured Systems (Semiconductors and Semimetals, 35, 191). Academic Press.
- <span id="page-116-2"></span>[36] B¨uttiker, M., Imry, Y., Landauer, R., and Pinhas, S. (1985) Phys. Rev. B, 31, 6207.
- <span id="page-116-4"></span><span id="page-116-3"></span>[37] Datta, S. (1995) Electronic Transport in Mesoscopic Systems. Cambridge UP.
- <span id="page-116-5"></span>[38] Klaß, U., Dietsche, W., v. Klitzing, K., and Ploog, K. (1991) Z. Phys. B:Cond. Matt., 82, 351.
- <span id="page-116-6"></span>[39] B¨uttiker, M. (1988) Phys. Rev. B, 38, 9375.
- [40] Hashimoto, K., Sohrmann, C., Wiebe, J., Inaoka, T., Meier, F., Hirayama, Y., R¨omer, R. A., Wiesendanger, R., and Morgenstern, M. (2008) Phys. Rev. Lett., 101, 256802.
- <span id="page-116-7"></span>[41] Sondhi, S. L., Girvin, S. M., Carini, J. P., and Shahar, D. (1997) Rev. Mod. Phys., 69, 315.
- <span id="page-116-9"></span><span id="page-116-8"></span>[42] Sachdev, S. (1999) Quantum Phase Transitions. Cambridge UP.
- <span id="page-116-10"></span>[43] Wei, H. P., Tsui, D. C., Paalanen, M. A., and Pruisken, A. M. M. (1988) Phys. Rev. Lett., 61, 1294.
- <span id="page-116-11"></span>[44] Wei, H. P., Engel, L. W., and Tsui, D. C. (1994) Phys. Rev. B, 50, 14609.
- [45] Li, W., Csathy, A., Tsui, D. C., Pfeiffer, L. N., and West, K. W. (2005) Phys. Rev. Lett., 94, 206807.
- <span id="page-116-12"></span>[46] Li, W., Vicente, C. L., Xia, J. S., Pan, W., Tsui, D. C., Pfeiffer, L. N., and West, K. W. (2009) Phys. Rev. Lett., 102, 216801.
- <span id="page-116-14"></span><span id="page-116-13"></span>[47] Chalker, J. T. and Coddington, P. D. (1988) J. Phys. C, 21, 2665.
- <span id="page-116-15"></span>[48] Huckestein, B. (1995) Rev. Mod. Phys., 67, 357.
- <span id="page-116-16"></span>[49] Huckestein, B. and Backhaus, M. (1999) Phys. Rev. Lett., 82, 5100.
- <span id="page-116-17"></span>[50] Slevin, K. and Ohtsuki, T. (2009) Phys. Rev. B, 80, 041304.
- <span id="page-116-18"></span>[51] Brey, L. and Fertig, H. (2006) Phys. Rev. B, 73, 195408.
- <span id="page-116-19"></span>[52] Mahan, G. D. (1993) Many-Particle Physics. Plenum Press, 2nd Ed.
- [53] Giuliani, G. F. and Vignale, G. (2005) Quantum Theory of Electron Liquids. Cambridge UP.

- <span id="page-117-1"></span><span id="page-117-0"></span>[54] Kallin, C. and Halperin, B. I. (1984) Phys. Rev. B, 30, 5655.
- <span id="page-117-2"></span>[55] Iyengar, A., Wang, J., Fertig, H. A., and Brey, L. (2007) Phys. Rev. B, 75, 125430.
- <span id="page-117-3"></span>[56] Rold´an, R., Fuchs, J.-N., and Goerbig, M. O. (2009) Phys. Rev. B, 80, 085408.
- <span id="page-117-4"></span>[57] Wigner, E. (1934) Phys. Rev., 102, 46.
- <span id="page-117-5"></span>[58] Fukuyama, H., Platzman, P. M., and Anderson, P. W. (1979) Phys. Rev. B, 19, 5211.
- [59] Andrei, E. Y., Deville, G., Glattli, D. C., Williams, F. I. B., Paris, E., and Etienne, B. (1988) Phys. Rev. Lett., 60, 2765.
- <span id="page-117-6"></span>[60] Gervais, G., Engel, L. W., Stormer, H. L., Tsui, D. C., Baldwin, K. W., West, K. W., and Pfeiffer, L. N. (2004) Phys. Rev. Lett., 93, 266804.
- <span id="page-117-8"></span><span id="page-117-7"></span>[61] Cooper, N. R. (2008) Advances in Physics, 57, 539.
- <span id="page-117-9"></span>[62] Haldane, F. D. M. (1983) Phys. Rev. Lett., 51, 605.
- <span id="page-117-10"></span>[63] Haldane, F. D. M. and Rezayi, E. H. (1985) Phys. Rev. Lett., 54, 237.
- <span id="page-117-11"></span>[64] Fano, G., Ortolani, F., and Colombo, E. (1986) Phys. Rev. B, 34, 2670.
- [65] Girvin, S. M., MacDonald, A. H., and Platzman, P. M. (1986) Phys. Rev. B, 33, 2481.
- <span id="page-117-12"></span>[66] Tinkham, M. (2004) Introduction to Superconductivity. Dover Publications, 2nd Ed.
- <span id="page-117-14"></span><span id="page-117-13"></span>[67] Girvin, S. M. and Jach, T. (1984) Phys. Rev. B, 29, 5617.
- [68] de Picciotto, R., Reznikov, M., Heidblum, M., Umansky, V., Bunin, G., and Mahalu, D. (1997) Nature, 389, 162.
- <span id="page-117-15"></span>[69] Saminadayar, L., Glattli, D. C., Jin, Y., and Etienne, B. (1997) Phys. Rev. Lett., 79, 2526.
- <span id="page-117-16"></span>[70] Nayak, C., Simon, S. H., Stern, A., Friedman, M., and Das Sarma, S. (2008) Rev. Mod. Phys., 80, 1083.
- <span id="page-117-18"></span><span id="page-117-17"></span>[71] Mermin, N. D. (1979) Rev. Mod. Phys., 51, 591.
- <span id="page-117-19"></span>[72] Haldane, F. D. M. (1991) Phys. Rev. Lett., 67, 937.
- [73] Luhman, D. R., Pan, W., Tsui, D. C., Pfeiffer, L. N., Baldwin, K. W., and West, K. W. (2008) Phys. Rev. Lett., 101, 266804.
- <span id="page-117-20"></span>[74] Shabani, J., Gokmen, T., and Shayegan, M. (2009) Phys. Rev. Lett., 103, 046805.

- <span id="page-118-1"></span><span id="page-118-0"></span>[75] Halperin, B. I. (1984) Phys. Rev. Lett., 52, 1583.
- <span id="page-118-2"></span>[76] Jain, J. K. (2007) Composite Fermions. Cambridge UP.
- <span id="page-118-3"></span>[77] Lopez, A. and Fradkin, E. (1991) Phys. Rev. B, 44, 5246.
- <span id="page-118-4"></span>[78] Halperin, B. I., Lee, P. A., and Read, N. (1993) Phys. Rev. B, 47, 7312.
- <span id="page-118-5"></span>[79] Heinonen, E., O. (1998) Composite Fermions. World Scientific.
- <span id="page-118-6"></span>[80] Rezayi, E. H. and Read, N. (1994) Phys. Rev. Lett., 72, 100.
- [81] Papi´c, Z., M¨oller, G., Milovanovi´c, M., Regnault, N., and Goerbig, M. O. (2009) Phys. Rev. B, 79, 245327.
- <span id="page-118-8"></span><span id="page-118-7"></span>[82] W´ojs, A. and Quinn, J. J. (2000) Philos. Mag. B, 80, 1405.
- <span id="page-118-9"></span>[83] Kitaev, A. Y. (2003) Ann. Phys. (N.Y.), 303, 2.
- <span id="page-118-10"></span>[84] Halperin, B. I. (1983) Helv. Phys. Acta, 56, 75.
- <span id="page-118-11"></span>[85] Abolfath, M., Belkhir, L., and Nafari, N. (1997) Phys. Rev. B, 55, 10643.
- [86] Sondhi, S. L., Karlhede, A., Kivelson, S. A., and Rezayi, E. H. (1993) Phys. Rev. B, 47, 16419.
- <span id="page-118-12"></span>[87] Moon, K., Mori, H., Yang, K., Girvin, S. M., MacDonald, A. H., Zheng, I., Yoshioka, D., and Zhang, S.-C. (1995) Phys. Rev. B, 51, 5143.
- <span id="page-118-14"></span><span id="page-118-13"></span>[88] Fertig, H. A. (1989) Phys. Rev. B, 40, 1087.
- <span id="page-118-15"></span>[89] Wen, X.-G. and Zee, A. (1992) Phys. Rev. Lett, 69, 1811.
- <span id="page-118-16"></span>[90] Ezawa, Z. F. and Iwazaki, A. (1993) Phys. Rev. B, 47, 7295.
- <span id="page-118-17"></span>[91] Spielman, I. B., Eisenstein, J. P., Pfeiffer, L. N., and West, K. W. (2000) Phys. Rev. Lett., 84, 5808.
- [92] Kellogg, M., Eisenstein, J. P., and an K. W. West, L. N. P. (2004) Phys. Rev. Lett., 036801.
- <span id="page-118-19"></span><span id="page-118-18"></span>[93] Tutuc, E., Shayegan, M., and Huse, D. A. (2004) Phys. Rev. Lett, 93, 036802.
- <span id="page-118-20"></span>[94] Nomura, K. and MacDonald, A. H. (2006) Phys. Rev. Lett., 96, 256602.
- <span id="page-118-21"></span>[95] Goerbig, M. O., Dou¸cot, B., and Moessner, R. (2006) Phys. Rev. B, 74, 161407.
- <span id="page-118-22"></span>[96] Alicea, J. and Fisher, M. P. A. (2006) Phys. Rev. B, 74, 075422.
- [97] Yang, K., Das Sarma, S., and MacDonald, A. H. (2006) Phys. Rev. B, 74, 075423.

<span id="page-119-2"></span><span id="page-119-1"></span><span id="page-119-0"></span>![](images/_page_119_Picture_0.jpeg)

<span id="page-119-9"></span><span id="page-119-8"></span><span id="page-119-7"></span><span id="page-119-6"></span><span id="page-119-5"></span><span id="page-119-4"></span><span id="page-119-3"></span>Gossard, A. C. (1997) Phys. Rev. B, 56, R12776. [108] Kukushkin, I. K., v. Klitzing, K., and Eberl, K. (1999) Phys. Rev. Lett., 82, 3665.

<span id="page-119-12"></span><span id="page-119-11"></span><span id="page-119-10"></span>[109] Goerbig, M. O. and Regnault, N. (2007) Phys. Rev. B, 75, 241405. [110] Wen, X.-G. and Zee, A. (1992) Phys. Rev. B, 46, 2290. [111] Wallace, P. R. (1947) Phys. Rev., 71, 622. [112] Klein, O. (1929) Z. Phys., 53, 157.

<span id="page-119-14"></span><span id="page-119-13"></span>

![](images/_page_120_Picture_0.jpeg)

 $R_L \sim \mu_3 - \mu_2 = 0$ 

 $\mu_6^{\phantom{0}=}\,\mu_5^{\phantom{0}=}\,\mu_R^{\phantom{0}}$ 

3

 $\mu_3 = \mu_L$ 

 $R_{H} \sim \mu_{5} - \mu_{3} = \mu_{R} - \mu_{L}$ 

 $\mu_2 = \mu_{\underline{L}} 2$ 

6

**→** 

![](images/_page_121_Picture_0.jpeg)

-5

0.15 ع

0.10 (5/e) 0.05 (9)

80

-20

0 V<sub>g</sub> (V)

20

40

10

 $^4$ B(T)  $\stackrel{\dot{6}}{\sim} 1/\nu$ 

22 60

-40

40 V<sub>g</sub> (V)

18

-60

2

V<sub>g</sub>=15V T=30mK

b

0.5

20

R<sub>xy</sub> (h/e<sup>2</sup>)

-0.5

-80

DOS

n = -3

B=97 T=1.0

60

![](images/_page_122_Picture_0.jpeg)

-4

filled levels

n=-3 n=-4

n=-1

n=-2

![](images/_page_123_Picture_0.jpeg)

1.00

0.98

0.96

0.4 T 1.9 K

20

30

40

50

Energy (meV)

10

Relative transmission

(B)

 $\widetilde{c}\sqrt{2e\hbar B_{\perp}}$ 

60

70

80

![](images/_page_124_Picture_0.jpeg)

electron

in VB

![](images/_page_125_Figure_0.jpeg)

![](images/_page_126_Figure_0.jpeg)

![](images/_page_127_Figure_0.jpeg)

![](images/_page_128_Figure_0.jpeg)

![](images/_page_129_Figure_0.jpeg)

![](images/_page_130_Picture_0.jpeg)